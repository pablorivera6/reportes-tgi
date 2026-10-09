"""El logger de campo exporta la data cruda en .xls (Excel 97-2003), p.ej.
'28-09-26 RAMAL TAUSA ... 2+420.xls'. El cargador web solo aceptaba .xlsx, así
que el selector de archivos los dejaba en gris y no había forma de subirlos
(Tausa, 2026-10). Ahora se aceptan y, al guardarlos, se convierten a .xlsx para
que el resto del motor (openpyxl / pandas) no cambie."""
import os
import re
import shutil

import pandas as pd

from cips_lrs import procesar_cips_lrs, tecnico_de_archivos
from xls_compat import a_xlsx

RAIZ = os.path.join(os.path.dirname(__file__), "..")
FIX = os.path.join(os.path.dirname(__file__), "fixtures")


def _copia(tmp_path, nombre):
    destino = os.path.join(tmp_path, nombre)
    shutil.copy(os.path.join(FIX, nombre), destino)
    return destino


def test_xls_se_convierte_con_sus_hojas_y_valores(tmp_path):
    xls = _copia(tmp_path, "cips_logger.xls")
    nuevo = a_xlsx(xls)
    assert nuevo.endswith(".xlsx") and os.path.exists(nuevo)
    ref = pd.read_excel(os.path.join(FIX, "cips_logger.xlsx"), sheet_name=None)
    conv = pd.read_excel(nuevo, sheet_name=None)
    assert list(conv) == ["Survey Data", "DCP Data", "Survey Info"]
    for hoja in ref:
        pd.testing.assert_frame_equal(conv[hoja], ref[hoja], check_dtype=False)


def test_xlsx_no_se_toca(tmp_path):
    xlsx = _copia(tmp_path, "cips_logger.xlsx")
    assert a_xlsx(xlsx) == xlsx


def test_cips_desde_xls_igual_que_desde_xlsx(tmp_path, shp_real):
    xls = a_xlsx(_copia(tmp_path, "cips_logger.xls"))
    xlsx = _copia(tmp_path, "cips_logger.xlsx")
    df_xls = procesar_cips_lrs([xls], shp_real)
    df_xlsx = procesar_cips_lrs([xlsx], shp_real)
    assert len(df_xls) == len(df_xlsx) > 0
    for col in ("On_mV", "Off_mV", "Abscisa_m"):
        if col in df_xlsx:
            assert list(df_xls[col]) == list(df_xlsx[col]), col
    assert tecnico_de_archivos([xls]) == "EVELIO ALVAREZ"


def test_cargadores_de_data_cruda_aceptan_xls():
    src = open(os.path.join(RAIZ, "streamlit_app.py"), encoding="utf-8").read()
    cips = re.search(r'file_uploader\("Excel CIPS", type=\[([^\]]*)\]', src)
    assert cips and '"xls"' in cips.group(1)
    campo = re.search(r'file_uploader\("Data cruda de campo[^"]*",\s*type=\[([^\]]*)\]', src)
    assert campo and '"xls"' in campo.group(1)
    # todo lo subido pasa por la conversión antes de llegar al motor
    tmp = src[src.index("def _tmp_files"):src.index("# ── Autollenado")]
    assert "a_xlsx(" in tmp


def test_xlrd_en_requirements():
    req = open(os.path.join(RAIZ, "requirements.txt"), encoding="utf-8").read()
    assert re.search(r"^xlrd", req, re.M)


def test_xls_ilegible_da_mensaje_claro(tmp_path):
    import pytest
    malo = os.path.join(tmp_path, "roto.xls")
    with open(malo, "wb") as f:
        f.write(b"esto no es un excel")
    with pytest.raises(ValueError, match=r"roto\.xls.*\.xlsx"):
        a_xlsx(malo)
