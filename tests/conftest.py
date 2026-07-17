import os
import glob
import numpy as np
import pandas as pd
import pytest
import shapefile  # pyshp

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def shp_real():
    """Ruta a un shapefile real del bundle (R_ACA.shp)."""
    ruta = os.path.join(SRC, "shapefiles", "R_ACA.shp")
    assert os.path.exists(ruta), f"No existe {ruta}"
    return ruta


@pytest.fixture
def archivos_cips(tmp_path, shp_real):
    """Crea 2 Excel CIPS sintéticos con puntos a lo largo del shapefile real.
    Devuelve la lista de rutas."""
    sf = shapefile.Reader(shp_real)
    pts = sf.shapes()[0].points  # (lon, lat) en WGS84
    muestra = pts[:60]
    lons = [p[0] for p in muestra]
    lats = [p[1] for p in muestra]
    n = len(lons)
    rng = np.random.default_rng(42)

    rutas = []
    for k in range(2):
        ini = k * n
        survey = pd.DataFrame({
            "Data No": range(ini + 1, ini + n + 1),
            "Dist From Start": np.arange(n) * 10.0,
            "On Voltage": -1.1 + rng.standard_normal(n) * 0.02,
            "Off Voltage": -0.9 + rng.standard_normal(n) * 0.02,
            "Latitude": lats,
            "Longitude": lons,
            "Comment": [""] * n,
            "DCP/Feature/DCVG Anomaly": [""] * n,
        })
        dcp = pd.DataFrame({
            "Data No": [ini + 1],
            "Device ID": ["ABC123"],
            "Comments": ["inicio de tramo"],
        })
        ruta = os.path.join(tmp_path, f"cips_{k}.xlsx")
        with pd.ExcelWriter(ruta, engine="openpyxl") as w:
            survey.to_excel(w, sheet_name="Survey Data", index=False)
            dcp.to_excel(w, sheet_name="DCP Data", index=False)
        rutas.append(ruta)
    return rutas
