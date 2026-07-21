"""La abscisa CIPS debe ser IDÉNTICA a la de la app original proceso-cips:
PK geométrico (GPS proyectado sobre la traza), ordenado ascendente.

Regresión de la reversión del experimento 'abscisa por etiqueta DCP' que
inundaba bloques de puntos con la misma abscisa en surveys continuos.
"""
import os

import pandas as pd

from cips_lrs import procesar_cips_lrs
from mod_unificar import ejecutar_unificar
from mod_cips_lrs import ejecutar_cips_lrs


def test_abscisa_identica_al_motor_original(archivos_cips, shp_real, tmp_path):
    # Motor original (verbatim de proceso-cips): unificar + LRS + export
    carpeta = str(tmp_path / "orig")
    os.makedirs(carpeta)
    import shutil
    for a in archivos_cips:
        shutil.copy(a, carpeta)
    unif = ejecutar_unificar(carpeta)
    salida = ejecutar_cips_lrs(carpeta, unif, shp_real)
    df_orig = pd.read_excel(salida, sheet_name="Survey Data")

    # Nuestro wrapper
    df_wrap = procesar_cips_lrs(archivos_cips, shp_real)

    pk_orig = df_orig["PK_geom_m"].round(3).tolist()
    pk_wrap = df_wrap["PK_geom_m"].round(3).tolist()
    assert pk_wrap == pk_orig, (
        f"PK difiere del original: wrap[:5]={pk_wrap[:5]} orig[:5]={pk_orig[:5]}")

    # Y el orden es ascendente por PK, como el original
    assert pk_wrap == sorted(pk_wrap)

    # Sin columnas del experimento de etiquetas
    assert "Abscisa_final_m" not in df_wrap.columns
    assert "Abscisa_label_m" not in df_wrap.columns
