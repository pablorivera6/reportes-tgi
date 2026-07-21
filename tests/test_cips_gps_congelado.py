"""CIPS con GPS congelado: si el equipo no actualiza el GPS (todas las
lecturas con la misma coordenada), la proyección sobre la traza colapsa a un
solo PK (p.ej. todo 0). En ese caso la abscisa debe caer al odómetro del
equipo ('Dist From Start' → PK_equipo), anclado a la etiqueta 'pk X+YYY' si
existe. Con GPS normal el comportamiento sigue siendo IDÉNTICO al original
(lo garantiza test_cips_equivalencia_original)."""
import os

import pandas as pd
import shapefile

from cips_lrs import procesar_cips_lrs


def _archivo_gps_congelado(tmp_path, shp_real, con_ancla):
    sf = shapefile.Reader(shp_real)
    lon0, lat0 = sf.shapes()[0].points[0]
    n = 12
    survey = pd.DataFrame({
        "Data No": range(1, n + 1),
        "Dist From Start": [i * 5.0 for i in range(n)],   # odómetro avanza
        "On Voltage": [-1.6] * n,
        "Off Voltage": [-1.0] * n,
        "Latitude": [lat0] * n,      # GPS congelado: TODAS iguales
        "Longitude": [lon0] * n,
        "Comment": [None] * n,
        "DCP/Feature/DCVG Anomaly": [None] * n,
    })
    dcp = pd.DataFrame({
        "Data No": [1],
        "DCP/Feature/Anomaly": ["Flag"],
        "Device ID": [None],
        "Comments": ["salida valvula pk 2+000" if con_ancla else "salida valvula"],
    })
    ruta = os.path.join(tmp_path, f"cips_congelado_{con_ancla}.xlsx")
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        survey.to_excel(w, sheet_name="Survey Data", index=False)
        dcp.to_excel(w, sheet_name="DCP Data", index=False)
    return ruta


def test_gps_congelado_usa_odometro(tmp_path, shp_real):
    ruta = _archivo_gps_congelado(tmp_path, shp_real, con_ancla=False)
    df = procesar_cips_lrs([ruta], shp_real)
    pks = df["PK_geom_m"].round(1).tolist()
    assert pks == [i * 5.0 for i in range(12)], f"abscisas: {pks}"
    assert df.attrs.get("fuente_abscisa") == "EQUIPO"


def test_gps_congelado_ancla_en_etiqueta_pk(tmp_path, shp_real):
    ruta = _archivo_gps_congelado(tmp_path, shp_real, con_ancla=True)
    df = procesar_cips_lrs([ruta], shp_real)
    pks = df["PK_geom_m"].round(1).tolist()
    # ancla: la fila de 'pk 2+000' (Dist=0) queda en 2000 y de ahí avanza
    assert pks == [2000 + i * 5.0 for i in range(12)], f"abscisas: {pks}"
