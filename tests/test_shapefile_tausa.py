"""R_TAU.shp traía DOS líneas a ~130 km: Ramal Tausa (Cundinamarca, D3) y
Ramal Tauramena (Casanare, D4). Tausa (R_TAUS) quedaba "sin shapefile" y un
CIPS de Tauramena se habría abscisado sobre las dos líneas pegadas (el motor
las une en una sola). Cada ramal tiene ahora su propia traza (Tausa, 2026-10)."""
import math
import os

import numpy as np
import pandas as pd
import pytest
import shapefile

from cips_infra import InfraTramos
from cips_lrs import procesar_cips_lrs

RAIZ = os.path.join(os.path.dirname(__file__), "..")


def _km(a, b):
    return math.hypot((a[0] - b[0]) * 111 * math.cos(math.radians(a[1])),
                      (a[1] - b[1]) * 111)


@pytest.fixture(scope="module")
def infra():
    return InfraTramos()


def test_tausa_tiene_su_traza(infra):
    shp = infra.shapefile(empresa="TGI", tramo="Ramal Tausa", distrito="D3")
    assert shp, "Ramal Tausa sigue sin shapefile"
    sf = shapefile.Reader(shp)
    assert len(sf.shapes()) == 1
    xmin, ymin, xmax, ymax = sf.bbox
    # municipio de Tausa ~ (5.19 N, -73.89 W)
    assert -73.95 < xmin and xmax < -73.85 and 5.1 < ymin and ymax < 5.25


def test_tauramena_solo_tiene_su_traza(infra):
    sf = shapefile.Reader(os.path.join(RAIZ, "shapefiles", "R_TAU.shp"))
    assert len(sf.shapes()) == 1
    xmin, ymin, xmax, ymax = sf.bbox
    # municipio de Tauramena ~ (5.02 N, -72.75 W)
    assert -72.8 < xmin and xmax < -72.7


def test_ninguna_traza_del_listado_junta_lineas_lejanas(infra):
    """Una traza con partes separadas se une en una sola línea con un salto
    falso: las abscisas salen corridas sin ningún error."""
    for id_tramo in sorted(set(infra.df["ID TRAMO"].astype(str))):
        ruta = os.path.join(RAIZ, "shapefiles", id_tramo + ".shp")
        if not os.path.exists(ruta):
            continue
        partes = [s.points for s in shapefile.Reader(ruta).shapes() if s.points]
        for i, p in enumerate(partes):
            resto = [q for j, o in enumerate(partes) if j != i for q in o]
            if resto:
                cerca = min(_km(e, q) for e in (p[0], p[-1]) for q in resto)
                assert cerca < 2, f"{id_tramo}: parte {i} a {cerca:.0f} km del resto"


def test_cips_de_tausa_se_abscisa_sobre_su_ramal(infra, tmp_path):
    shp = infra.shapefile(empresa="TGI", tramo="Ramal Tausa", distrito="D3")
    pts = shapefile.Reader(shp).shapes()[0].points
    n = len(pts)
    survey = pd.DataFrame({
        "Data No": range(1, n + 1), "Dist From Start": np.arange(n) * 10.0,
        "On Voltage": [-1.1] * n, "Off Voltage": [-0.9] * n,
        "Latitude": [p[1] for p in pts], "Longitude": [p[0] for p in pts],
        "Comment": [""] * n, "DCP/Feature/DCVG Anomaly": [""] * n})
    ruta = os.path.join(tmp_path, "tausa.xlsx")
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        survey.to_excel(w, sheet_name="Survey Data", index=False)
        pd.DataFrame({"Data No": [1], "Device ID": ["ABC123"],
                      "Comments": ["inicio"]}).to_excel(
            w, sheet_name="DCP Data", index=False)
    df = procesar_cips_lrs([ruta], shp)
    largo_km = sum(_km(a, b) for a, b in zip(pts, pts[1:]))
    assert df["PK_geom_m"].min() < 50
    assert df["PK_geom_m"].max() < largo_km * 1000 * 1.3   # sin el salto de ~130 km
