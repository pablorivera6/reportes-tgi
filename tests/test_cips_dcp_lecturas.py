"""Lecturas DCP (Metal IR / Far Ground / Near Ground) del archivo del equipo
deben llegar a las columnas L-Q de la hoja Potenciales CIPS, en la fila del
poste correspondiente (match por Data No), en mV."""
import os

import pandas as pd
import shapefile

from cips_lrs import procesar_cips_lrs
from cips_adapter import lrs_df_a_cips_dicts
from generator import ReportGenerator, resource_path


def _archivo_con_dcp(tmp_path, shp_real):
    sf = shapefile.Reader(shp_real)
    pts = sf.shapes()[0].points[:6]
    lons = [p[0] for p in pts]
    lats = [p[1] for p in pts]
    n = len(pts)
    survey = pd.DataFrame({
        "Data No": range(1, n + 1),
        "Dist From Start": [i * 10.0 for i in range(n)],
        "On Voltage": [-1.5] * n,
        "Off Voltage": [-1.0] * n,
        "Latitude": lats, "Longitude": lons,
        "Comment": [None] * n,
        "DCP/Feature/DCVG Anomaly": [None] * n,
    })
    dcp = pd.DataFrame({
        "Data No": [3, 3, 3, 5],
        "DCP/Feature/Anomaly": ["4+000: Far Ground reading", "4+000: Metal IR",
                                "4+000: Near Ground reading", "Highway"],
        "Value1": [-2.06038, -0.07567, -2.13013, 0],
        "Value2": [-1.18283, -0.01392, -1.18752, 0],
        "Value3": [1e23, 0.568, 1e23, 0],
        "Device ID": [None] * 4,
        "Comments": [None, None, None, "cruce via"],
    })
    ruta = os.path.join(tmp_path, "cips_dcp.xlsx")
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        survey.to_excel(w, sheet_name="Survey Data", index=False)
        dcp.to_excel(w, sheet_name="DCP Data", index=False)
    return ruta


def test_lecturas_dcp_llegan_a_columnas_del_formato(tmp_path, shp_real):
    ruta = _archivo_con_dcp(tmp_path, shp_real)
    df = procesar_cips_lrs([ruta], shp_real)
    dicts = lrs_df_a_cips_dicts(df)

    con_metal = [d for d in dicts if d.get('metal_on') is not None]
    assert len(con_metal) == 1, "exactamente el poste con lecturas DCP"
    d = con_metal[0]
    assert round(d['metal_on'], 2) == -75.67      # V -> mV
    assert round(d['metal_off'], 2) == -13.92
    assert round(d['far_on'], 2) == -2060.38
    assert round(d['far_off'], 2) == -1182.83
    assert round(d['near_on'], 2) == -2130.13
    assert round(d['near_off'], 2) == -1187.52

    gen = ReportGenerator(resource_path("CIPS EN BLANCO.xlsx"))
    gen.fill_cips(dicts)
    ws = gen.wb['Potenciales CIPS']
    fila = next(r for r in range(12, 12 + len(dicts))
                if ws.cell(row=r, column=12).value is not None)
    assert round(ws.cell(row=fila, column=12).value, 2) == -75.67   # L Metal ON
    assert round(ws.cell(row=fila, column=13).value, 2) == -13.92   # M Metal OFF
    assert round(ws.cell(row=fila, column=14).value, 2) == -2060.38  # N Far ON
    assert round(ws.cell(row=fila, column=15).value, 2) == -1182.83  # O Far OFF
    assert round(ws.cell(row=fila, column=16).value, 2) == -2130.13  # P Near ON
    assert round(ws.cell(row=fila, column=17).value, 2) == -1187.52  # Q Near OFF
