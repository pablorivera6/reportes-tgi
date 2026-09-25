"""El registro fotográfico se pide distinto según el tipo de inspección.

En CIPS y PAP el técnico sube TODAS las fotos en una sola casilla (y en el
entregable quedan en una sola carpeta `06_RF`). En DCVG se siguen separando por
elemento, porque ahí el registro por defecto/poste es lo que sustenta el
informe. La web de carga (`web_carga/data.js`) sale de este mismo catálogo.
"""
import entrega


def _rf(tipo):
    return [c for c in entrega.CATALOGO[tipo] if c["grupo"] == "rf"]


def test_cips_y_pap_tienen_una_sola_casilla_de_fotos():
    for tipo in ("CIPS", "PAP"):
        casillas = _rf(tipo)
        assert len(casillas) == 1, f"{tipo}: {[c['clave'] for c in casillas]}"
        assert casillas[0]["clave"] == "foto_rf"
        # sin subcarpeta: todo cae en 06_RF
        assert not casillas[0]["sub"]


def test_dcvg_mantiene_las_fotos_separadas_por_elemento():
    subs = {c["sub"] for c in _rf("DCVG")}
    assert subs == {"Defectos", "Postes", "Interfases", "Hallazgos",
                    "Panoramicas"}


def test_las_fotos_van_a_la_carpeta_rf_en_todos_los_tipos():
    for tipo in entrega.CATALOGO:
        for c in _rf(tipo):
            assert c["carpeta"] == "rf"
            assert c["tipos"] == ["jpg", "jpeg", "png", "heic"]
