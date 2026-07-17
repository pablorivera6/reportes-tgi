"""Regresión: abscisas repetidas al procesar varios archivos CIPS.

Causa raíz: cada 'Procesar CIPS' reprocesaba los archivos y ANEXABA
(extend) los registros a los ya guardados, duplicando todo el lote.
Además, si los exportes del logger se solapan (exportes acumulativos),
las filas idénticas entraban dos veces al motor.
"""
import os
import shutil
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_archivo_solapado_no_duplica_filas(archivos_cips, shp_real, tmp_path):
    from cips_lrs import procesar_cips_lrs
    copia = os.path.join(tmp_path, "reexport_cips_0.xlsx")
    shutil.copy(archivos_cips[0], copia)

    df_base = procesar_cips_lrs([archivos_cips[0]], shp_real)
    df_solape = procesar_cips_lrs([archivos_cips[0], copia], shp_real)
    assert len(df_solape) == len(df_base), (
        "Filas idénticas de exportes solapados deben deduplicarse")


def test_streamlit_reemplaza_en_vez_de_acumular():
    src = open(os.path.join(SRC, "streamlit_app.py"), encoding="utf-8").read()
    assert "data['cips'].extend" not in src, (
        "Procesar CIPS debe reemplazar data['cips'], no acumular")


def test_desktop_reemplaza_en_vez_de_acumular():
    import inspect
    g = types.ModuleType("google.generativeai")
    g.configure = lambda **k: None
    g.GenerativeModel = object
    g.list_models = lambda: []
    sys.modules["google"] = types.ModuleType("google")
    sys.modules["google.generativeai"] = g

    from app import AppWindow
    src = inspect.getsource(AppWindow.load_cips)
    assert "self.data['cips'].extend" not in src, (
        "load_cips debe reprocesar la lista completa y reemplazar, no acumular")
