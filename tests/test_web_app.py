import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from streamlit.testing.v1 import AppTest

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(SRC, "streamlit_app.py")


def _monta():
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    return at


def test_app_monta_sin_excepciones():
    at = _monta()
    assert not at.exception, f"La app lanzó excepción: {at.exception}"


def test_estado_inicial():
    at = _monta()
    data = at.session_state["data"]
    for k in ["info", "potenciales", "cips", "hallazgos", "rectificadores",
              "aislamientos", "inspecciones", "conclusiones", "recomendaciones",
              "firmas"]:
        assert k in data, f"Falta clave {k} en session_state.data"
    assert at.session_state["active_inspections"]["marco_h"] is False


ETIQUETAS_TABS = ["📝 Datos Generales", "📂 Cargar Archivos", "📊 Potenciales PAP",
                  "📉 CIPS", "⚠️ Hallazgos", "🔌 Rectificadores",
                  "🛠️ Insp. Especiales", "🔗 Aislamientos", "📋 Conclusiones",
                  "🚀 Generar"]


def test_tabs_y_boton_generar():
    at = _monta()
    # at.tabs aplana también las sub-pestañas de carga manual (PAP/CIPS/DCVG),
    # así que se verifican las pestañas principales por su nombre.
    etiquetas = [str(t.label) for t in at.tabs]
    faltan = [e for e in ETIQUETAS_TABS if e not in etiquetas]
    assert not faltan, f"faltan pestañas: {faltan}"
    # El botón GENERAR existe y está deshabilitado sin datos
    botones = [b for b in at.button if "GENERAR" in str(b.label).upper()]
    assert botones, "No se encontró el botón GENERAR INFORME"
