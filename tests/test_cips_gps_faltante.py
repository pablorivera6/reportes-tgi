"""Lecturas sin GPS: la posición se estima con una regresión contra el
odómetro ('Dist From Start'). Si a esa fila —o a cualquier otra— le falta
también el odómetro, sklearn reventaba con 'Input X contains NaN' y no se
procesaba nada (caso real: Ramal Ambalema)."""
import os

import numpy as np
import pandas as pd
import pytest
import shapefile

from cips_lrs import procesar_cips_lrs


def _archivo(tmp_path, shp_real, editar, n=40, nombre="cips.xlsx"):
    pts = shapefile.Reader(shp_real).shapes()[0].points[:n]
    survey = pd.DataFrame({
        "Data No": range(1, n + 1),
        "Dist From Start": np.arange(n) * 10.0,
        "On Voltage": [-1.2] * n,
        "Off Voltage": [-0.95] * n,
        "Latitude": [p[1] for p in pts],
        "Longitude": [p[0] for p in pts],
        "Comment": [None] * n,
        "DCP/Feature/DCVG Anomaly": [None] * n,
    })
    survey = editar(survey)
    dcp = pd.DataFrame({"Data No": [1], "DCP/Feature/Anomaly": ["Flag"],
                        "Device ID": [None], "Comments": ["inicio"]})
    ruta = os.path.join(tmp_path, nombre)
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        survey.to_excel(w, sheet_name="Survey Data", index=False)
        dcp.to_excel(w, sheet_name="DCP Data", index=False)
    return ruta


def test_fila_sin_gps_ni_odometro_se_ubica_entre_sus_vecinas(tmp_path, shp_real):
    def editar(s):
        s.loc[20, ["Latitude", "Longitude", "Dist From Start"]] = np.nan
        return s
    df = procesar_cips_lrs([_archivo(tmp_path, shp_real, editar)], shp_real)
    assert len(df) == 40                       # la lectura no se pierde
    assert df["PK_geom_m"].notna().all()
    ref = procesar_cips_lrs([_archivo(tmp_path, shp_real, lambda s: s,
                                      nombre="ref.xlsx")], shp_real)
    pk_ref = sorted(ref["PK_geom_m"])
    pk = sorted(df["PK_geom_m"])
    # la fila 20 cae entre la 19 y la 21 de la referencia
    assert pk_ref[19] - 1 <= pk[20] <= pk_ref[21] + 1


def test_odometro_vacio_en_fila_con_gps_no_rompe(tmp_path, shp_real):
    def editar(s):
        s.loc[5, "Dist From Start"] = np.nan          # tiene GPS, no odómetro
        s.loc[30, ["Latitude", "Longitude"]] = np.nan  # no GPS, sí odómetro
        return s
    df = procesar_cips_lrs([_archivo(tmp_path, shp_real, editar)], shp_real)
    assert len(df) == 40 and df["PK_geom_m"].notna().all()


def test_fila_sin_lectura_ni_posicion_se_descarta(tmp_path, shp_real):
    def editar(s):
        basura = {c: np.nan for c in s.columns}
        basura["Data No"] = 999
        return pd.concat([s, pd.DataFrame([basura])], ignore_index=True)
    df = procesar_cips_lrs([_archivo(tmp_path, shp_real, editar)], shp_real)
    assert len(df) == 40


def test_sin_ningun_gps_da_un_error_claro(tmp_path, shp_real):
    def editar(s):
        s["Latitude"] = np.nan
        s["Longitude"] = np.nan
        return s
    with pytest.raises(ValueError, match="GPS"):
        procesar_cips_lrs([_archivo(tmp_path, shp_real, editar)], shp_real)
