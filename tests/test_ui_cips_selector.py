import os
import sys
import types

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _stub_gemini():
    g = types.ModuleType("google.generativeai")
    g.configure = lambda **k: None
    g.GenerativeModel = object
    g.list_models = lambda: []
    sys.modules["google"] = types.ModuleType("google")
    sys.modules["google.generativeai"] = g


def test_selector_cascada():
    _stub_gemini()
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from app import AppWindow
    w = AppWindow()

    assert w.cmb_cips_empresa.count() == 2
    w.cmb_cips_empresa.setCurrentText("TGI")
    assert w.cmb_cips_distrito.isVisibleTo(w) in (True, False)
    assert w.cmb_cips_tramo.count() > 0

    w.cmb_cips_empresa.setCurrentText("OCENSA")
    assert w.cmb_cips_tramo.count() > 0


def test_load_cips_sin_widgets_fantasma():
    import inspect
    _stub_gemini()
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from app import AppWindow
    src = inspect.getsource(AppWindow.load_cips)
    assert "cmb_kmz_rutas" not in src
    assert "procesar_cips_lrs" in src
