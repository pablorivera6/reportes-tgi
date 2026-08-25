"""Los botones de KMZ y de paquete de entrega tienen que APARECER.

Regresión: el botón del paquete estaba anidado dentro del bloque del KMZ, y el
KMZ se armaba dentro de un `except` mudo. Cuando el KMZ no se podía construir
—un DCVG sin defectos, o los defectos sin GPS— desaparecían los dos botones sin
ningún mensaje, y el ingeniero se quedaba sin el entregable del contrato.
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from streamlit.testing.v1 import AppTest

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(SRC, "streamlit_app.py")

BTN_ZIP = "📦 Generar paquete de entrega (ZIP)"
BTN_KMZ = "🗺️ Descargar KMZ de la inspección"


def _con_informe(data_extra):
    """App con un informe ya generado en sesión y la data de la inspección."""
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    at.session_state["informe_bytes"] = b"xlsx simulado"
    at.session_state["informe_nombre"] = "DCVG_REP_R_ARM_03_25_PCC_Rev.A.xlsx"
    at.session_state["data"].update(data_extra)
    at.run()
    return at


def _etiquetas(at):
    return ([b.label for b in at.button]
            + [d.label for d in at.get("download_button")])


def _dcvg(**kw):
    base = {'info': {'tipo_inspeccion': 'DCVG', 'tramo': 'Ramal Armenia'},
            'dcvg_postes': [], 'dcvg_defectos': [], 'dcvg_hallazgos': []}
    base.update(kw)
    return base


def test_el_paquete_aparece_con_kmz():
    at = _con_informe(_dcvg(
        dcvg_postes=[{'pk_m': i * 1000, 'on': -1600, 'off': -1100,
                      'lat': 4.5 + i / 1000, 'lon': -75.7} for i in range(3)],
        dcvg_defectos=[{'pk_m': 1500, 'ol_re': 50.0, 'caracter': 'AA',
                        'lat': 4.52, 'lon': -75.72}]))
    assert not at.exception, at.exception
    etiquetas = _etiquetas(at)
    assert BTN_ZIP in etiquetas, "no salió el botón del paquete de entrega"
    assert BTN_KMZ in etiquetas, "no salió el botón del KMZ"


def test_el_paquete_aparece_aunque_no_haya_kmz():
    """Sin coordenadas no hay KMZ, pero el ZIP del contrato debe salir igual."""
    at = _con_informe(_dcvg(
        dcvg_defectos=[{'pk_m': 1500, 'ol_re': 50.0, 'caracter': 'AA',
                        'lat': None, 'lon': None}]))
    assert not at.exception, at.exception
    etiquetas = _etiquetas(at)
    assert BTN_ZIP in etiquetas, "sin KMZ desapareció el paquete de entrega"
    assert BTN_KMZ not in etiquetas
    # y explica por qué no hay KMZ, en vez de callarse
    assert any("Sin KMZ" in str(i.value) for i in at.info), \
        "no se explicó por qué falta el KMZ"


def test_el_paquete_aparece_en_una_inspeccion_sin_defectos():
    at = _con_informe(_dcvg(
        dcvg_postes=[{'pk_m': i * 1000, 'on': -1600, 'off': -1100,
                      'lat': 4.5 + i / 1000, 'lon': -75.7} for i in range(4)],
        dcvg_hallazgos=[{'abscisa_val': 2200, 'observaciones': 'cruce de caño',
                         'referencia': 'cruce', 'lat': 4.53, 'lon': -75.73}]))
    assert not at.exception, at.exception
    etiquetas = _etiquetas(at)
    assert BTN_ZIP in etiquetas and BTN_KMZ in etiquetas


def test_sin_informe_no_aparecen():
    at = AppTest.from_file(APP, default_timeout=180)
    at.run()
    assert BTN_ZIP not in _etiquetas(at)
