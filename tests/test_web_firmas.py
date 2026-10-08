"""Firmas en la web: REVISÓ y APROBÓ fijos (Alejandro Rivera, Ingeniero
Especialista CP4) y ELABORÓ elegido en la pestaña Generar entre los ingenieros
junior; sin elegirlo no se puede generar."""
import os

from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(__file__), "..", "streamlit_app.py")


def _monta():
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    return at


def test_selector_de_elaboro_y_firmas_fijas():
    at = _monta()
    sel = [s for s in at.selectbox if "elabor" in str(s.label).lower()]
    assert sel, "falta el selector de quién elaboró el informe"
    assert list(sel[0].options) == ["Pablo Rivera", "Edwin López", "Juan Gallego"]
    assert sel[0].value is None            # se pregunta, no viene preseleccionado
    src = open(APP, encoding="utf-8").read()
    assert '"reviso":  {"nombre": "Alejandro Rivera", "cargo": "Ingeniero Especialista CP4"' in src
    assert '"aprobo":  {"nombre": "Alejandro Rivera", "cargo": "Ingeniero Especialista CP4"' in src
    assert '"elaboro": {"nombre": "", "cargo": "Ingeniero Junior"' in src
    assert "FIRMAS_FIJAS[" not in src       # todo pasa por _firmas()


def test_generar_queda_deshabilitado_sin_elaboro():
    at = _monta()
    boton = [b for b in at.button if str(b.label).strip().lower() == "generar informe"][0]
    assert boton.disabled
