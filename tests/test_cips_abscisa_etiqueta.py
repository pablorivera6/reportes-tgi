"""CIPS: la abscisa debe salir de la etiqueta de campo (hoja DCP Data,
'pk X+YYY' / 'km X+YYY'), no de la proyección GPS.

Datos reales del RAMAL FLORIDA demostraron que el técnico graba postes
distintos ('pk 00+000' y 'pk 2+000') con la MISMA coordenada GPS, así que
proyectar el GPS los colapsa. La etiqueta es la fuente fiable; el GPS queda
solo como respaldo cuando no hay etiqueta.
"""
import os

import numpy as np
import pandas as pd
import shapefile

from cips_lrs import procesar_cips_lrs, _parse_abscisa_label


def test_parser_etiquetas():
    assert _parse_abscisa_label("pk 00+000: Pipe To Soil") == 0
    assert _parse_abscisa_label("pk 2+000: Pipe To Soil") == 2000
    assert _parse_abscisa_label("km 5+100 interface t") == 5100
    assert _parse_abscisa_label("km 5+120 junta 3 de") == 5120
    assert _parse_abscisa_label("PK4+000") == 4000
    assert _parse_abscisa_label("Junta 1 de entrada") is None
    assert _parse_abscisa_label(None) is None


def _archivo_cips_etiquetado(tmp_path, shp_real):
    """Survey con 6 puntos; DCP rotula dos postes con la MISMA coordenada
    GPS como 'pk 00+000' y 'pk 2+000' (el caso que rompía el GPS)."""
    sf = shapefile.Reader(shp_real)
    pts = sf.shapes()[0].points
    p0 = pts[0]  # misma coordenada para los dos primeros postes
    p1 = pts[min(20, len(pts) - 1)]
    lons = [p0[0], p0[0], p0[0], p1[0], p1[0], p1[0]]
    lats = [p0[1], p0[1], p0[1], p1[1], p1[1], p1[1]]
    survey = pd.DataFrame({
        "Data No": [1, 2, 3, 4, 5, 6],
        "Dist From Start": [0, 1, 2, 3, 4, 5],
        "On Voltage": [-1.1] * 6,
        "Off Voltage": [-0.9] * 6,
        "Latitude": lats, "Longitude": lons,
        "Comment": [None] * 6,
        "DCP/Feature/DCVG Anomaly": [None] * 6,
    })
    dcp = pd.DataFrame({
        "Data No": [1, 3, 4, 6],
        "DCP/Feature/Anomaly": ["pk 00+000: Pipe To Soil", "pk 2+000: Pipe To Soil",
                                "pk 4+000: Pipe To Soil", "km 5+100 junta: Pipe To Soil"],
        "Value1": [-1.1, -1.1, -1.1, -1.1],
        "Value2": [-0.9, -0.9, -0.9, -0.9],
        "Device ID": [None] * 4,
        "Comments": [None] * 4,
    })
    ruta = os.path.join(tmp_path, "cips_etiquetado.xlsx")
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        survey.to_excel(w, sheet_name="Survey Data", index=False)
        dcp.to_excel(w, sheet_name="DCP Data", index=False)
    return ruta


def test_abscisa_sale_de_la_etiqueta(tmp_path, shp_real):
    ruta = _archivo_cips_etiquetado(tmp_path, shp_real)
    df = procesar_cips_lrs([ruta], shp_real)
    assert "Abscisa_final_m" in df.columns
    absc = sorted(int(a) for a in df["Abscisa_final_m"].dropna().unique())
    # Los dos primeros postes (mismo GPS) deben quedar en 0 y 2000, NO colapsados.
    assert 0 in absc and 2000 in absc, f"abscisas: {absc}"
    assert 4000 in absc and 5100 in absc, f"abscisas: {absc}"
