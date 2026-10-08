"""Firmas en la web: REVISÓ fijo (Javier Jara, Ingeniero Residente), APROBÓ
fijo (Alejandro Rivera, Ingeniero Especialista CP4) y ELABORÓ elegido en la
pestaña Generar entre los ingenieros junior; sin elegirlo no se puede generar."""
import io
import os

import openpyxl

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
    assert '"reviso":  {"nombre": "Javier Jara", "cargo": "Ingeniero Residente"' in src
    assert '"aprobo":  {"nombre": "Alejandro Rivera", "cargo": "Ingeniero Especialista CP4"' in src
    assert '"elaboro": {"nombre": "", "cargo": "Ingeniero Junior"' in src
    assert "FIRMAS_FIJAS[" not in src       # todo pasa por _firmas()


def test_generar_queda_deshabilitado_sin_elaboro():
    at = _monta()
    boton = [b for b in at.button if str(b.label).strip().lower() == "generar informe"][0]
    assert boton.disabled


def test_informe_generado_lleva_las_tres_firmas():
    """De punta a punta: el informe que sale de la web trae a Javier Jara en
    REVISÓ y a Alejandro Rivera en APROBÓ en la hoja Informe."""
    at = _monta()
    at.session_state.data["info"].update({"tipo_inspeccion": "DCVG",
                                          "tramo": "Ramal Armenia"})
    at.session_state.data["dcvg_postes"] = [
        {"tipo": "Poste", "pk_m": pk, "on": -1600.0, "off": -1100.0,
         "lat": 4.9, "lon": -75.7} for pk in (1000, 2000)]
    at.session_state["elaboro_nombre"] = "Edwin López"
    at.run()
    [b for b in at.button if str(b.label).strip().lower() == "generar informe"][0].click().run()
    assert not at.exception, at.exception
    ws = openpyxl.load_workbook(io.BytesIO(at.session_state["informe_bytes"]))["Informe"]
    filas = {}
    for fila in ws.iter_rows():
        for c in fila:
            if isinstance(c.value, str):
                filas.setdefault(c.value.strip(), c.row)
    for valor in ("Edwin López", "Ingeniero Junior", "Javier Jara",
                  "Ingeniero Residente", "Alejandro Rivera",
                  "Ingeniero Especialista CP4"):
        assert valor in filas, valor
    # REVISÓ y APROBÓ en el mismo renglón del bloque, cada uno con su cargo
    assert filas["Javier Jara"] == filas["Alejandro Rivera"] == filas["Edwin López"]
    assert filas["Ingeniero Residente"] == filas["Ingeniero Especialista CP4"]
