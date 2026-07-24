"""coords_muestra: lat/lon medianos de los archivos CIPS, usados para sugerir
el tramo correcto cuando el seleccionado no tiene shapefile (caso real: el D2
'Ramal La Victoria' no trae shapefile; los datos son del D8 R_VICT)."""
import os

import pandas as pd

from cips_lrs import coords_muestra


def _archivo(tmp_path, nombre, lat, lon, n=10):
    survey = pd.DataFrame({
        "Data No": range(1, n + 1),
        "Latitude": [lat + i * 1e-4 for i in range(n)],
        "Longitude": [lon + i * 1e-4 for i in range(n)],
        "On Voltage": [-1.5] * n, "Off Voltage": [-1.0] * n,
    })
    ruta = os.path.join(tmp_path, nombre)
    with pd.ExcelWriter(ruta, engine="openpyxl") as w:
        survey.to_excel(w, sheet_name="Survey Data", index=False)
    return ruta


def test_coords_muestra_mediana(tmp_path):
    a = _archivo(tmp_path, "a.xlsx", 5.3147, -74.8474)
    b = _archivo(tmp_path, "b.xlsx", 5.3160, -74.8500)
    lat, lon = coords_muestra([a, b])
    assert 5.31 < lat < 5.32
    assert -74.86 < lon < -74.84


def test_coords_muestra_sin_datos(tmp_path):
    vacio = os.path.join(tmp_path, "v.xlsx")
    pd.DataFrame({"X": [1]}).to_excel(vacio, index=False)
    assert coords_muestra([vacio]) is None
