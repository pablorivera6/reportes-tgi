"""Logger en modo 'Always ON' (Tausa, 2026-09): el rectificador no se
interrumpió, así que no existe Instant OFF. El export trae UNA columna
'Voltage' (el ON) en vez de 'On Voltage'/'Off Voltage', o trae 'Off Voltage'
en 0.0 en todas las filas. Antes el ON se descartaba por el nombre de la
columna (el informe salía sin potenciales) y el 0 se escribía como un OFF
real de 0 mV."""
import os

import numpy as np
import pandas as pd
import pytest
import shapefile

from cips_lrs import procesar_cips_lrs, modo_rectificador
from cips_adapter import lrs_df_a_cips_dicts


def _puntos(n=40):
    pts = shapefile.Reader(os.path.join(os.path.dirname(__file__), "..",
                                        "shapefiles", "R_ACA.shp")).shapes()[0].points[:n]
    return [p[1] for p in pts], [p[0] for p in pts]


def _archivo(tmp_path, nombre, *, voltage=None, on=None, off=None, modo="Always ON",
             col_tiempo="On Time"):
    lats, lons = _puntos()
    n = len(lats)
    survey = {"Data No": range(1, n + 1), "Dist From Start": np.arange(n) * 10.0}
    if voltage is not None:
        survey["Voltage"] = voltage
    if on is not None:
        survey["On Voltage"] = on
    if off is not None:
        survey["Off Voltage"] = off
    survey.update({"Comment": [""] * n, "DCP/Feature/DCVG Anomaly": [""] * n,
                   col_tiempo: pd.date_range("2026-09-28 08:00", periods=n, freq="10s"),
                   "Latitude": lats, "Longitude": lons})
    ruta = os.path.join(tmp_path, nombre)
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        pd.DataFrame(survey).to_excel(w, sheet_name="Survey Data", index=False)
        pd.DataFrame({"Data No": [1], "Device ID": ["X"], "Comments": ["inicio"]}).to_excel(
            w, sheet_name="DCP Data", index=False)
        pd.DataFrame({"Field": ["Survey Type", "Rectifier Mode", "Technician Name"],
                      "Value": ["Continuous CIS", modo, "angel marin"]}).to_excel(
            w, sheet_name="Survey Info", index=False)
    return ruta


SHP = os.path.join(os.path.dirname(__file__), "..", "shapefiles", "R_ACA.shp")


def test_columna_voltage_es_el_on(tmp_path):
    a = _archivo(tmp_path, "solo_voltage.xlsx", voltage=[-0.84] * 40, col_tiempo="Time")
    df = procesar_cips_lrs([a], SHP)
    assert len(df) == 40
    assert df["On_mV"].round(1).eq(-840.0).all()
    assert df["On_mV_limpio"].round(1).eq(-840.0).all()
    assert df["Off_mV"].isna().all()
    assert df.attrs["sin_off"] == 40
    # la fecha sale de la columna 'Time' cuando no hay 'On Time'
    assert df["Fecha_dato"].eq("28/09/2026").all()


def test_off_en_cero_es_no_medido(tmp_path):
    a = _archivo(tmp_path, "off_cero.xlsx", on=[-0.80] * 40, off=[0.0] * 40)
    df = procesar_cips_lrs([a], SHP)
    assert df["On_mV"].round(1).eq(-800.0).all()
    assert df["Off_mV"].isna().all() and df["Off_mV_limpio"].isna().all()
    d = lrs_df_a_cips_dicts(df)
    assert all(p["on_limpio"] is not None and p["off_limpio"] is None for p in d)


def test_off_real_se_conserva(tmp_path):
    a = _archivo(tmp_path, "normal.xlsx", on=[-1.10] * 40, off=[-0.90] * 40, modo="Interrupted")
    df = procesar_cips_lrs([a], SHP)
    assert df["Off_mV"].round(1).eq(-900.0).all()
    assert df.attrs["sin_off"] == 0


def test_mezcla_de_archivos_always_on_y_normal(tmp_path):
    """Tausa: un archivo solo con 'Voltage' y otro con On/Off(=0). Al unirlos
    el ON de los dos debe estar; antes el del primero se perdía."""
    a = _archivo(tmp_path, "a.xlsx", voltage=[-0.84] * 40, col_tiempo="Time")
    b = _archivo(tmp_path, "b.xlsx", on=[-0.80] * 40, off=[0.0] * 40)
    df = procesar_cips_lrs([a, b], SHP)
    assert df["On_mV"].notna().all()
    assert df["Off_mV"].isna().all()


def test_modo_rectificador_de_los_archivos(tmp_path):
    a = _archivo(tmp_path, "a.xlsx", voltage=[-0.84] * 40)
    assert modo_rectificador([a]) == "Always ON"


def test_conclusiones_sin_off_lo_dicen():
    from conclusions import ConclusionGenerator
    pts = [{"abscisa_val": i * 10, "on_mv": -840.0, "off_mv": None,
            "on_limpio": -840.0, "off_limpio": None} for i in range(40)]
    cg = ConclusionGenerator([], [], [], [], {}, {"tramo": "Tausa", "tipo_ducto": "Ramal",
                                                  "tipo_inspeccion": "CIPS"}, cips=pts)
    texto = " ".join(cg.generar_conclusiones())
    assert "Instant Off" in texto and "0%" not in texto


def test_aviso_sin_off_en_la_web():
    from cips_lrs import aviso_sin_off
    msg = aviso_sin_off(n_sin_off=2751, total=2751, modo="Always ON")
    assert "Always ON" in msg and "Instant OFF" in msg and "-850" in msg
    assert aviso_sin_off(n_sin_off=0, total=100, modo="Interrupted") == ""
    src = open(os.path.join(os.path.dirname(__file__), "..", "streamlit_app.py"),
               encoding="utf-8").read()
    assert src.count("_aviso_cips_sin_off()") >= 2      # pestaña CIPS y Generar
