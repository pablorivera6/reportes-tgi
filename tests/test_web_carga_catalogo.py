"""`web_carga/data.js` es GENERADO desde `entrega.CATALOGO` por
`exportar_datos_carga.py`, que además quita las casillas que el técnico llena
dentro de FastField (esa data entra por el webhook, no la sube él). Aquí se
cuida que (1) Resistividades sea una de esas casillas en DCVG —va en el
subform_7 del mismo formulario FastField de DCVG— y (2) el data.js publicado
esté al día con el exportador (si alguien cambia el catálogo y no regenera,
este test lo dice)."""
import os
import re

import entrega
import exportar_datos_carga as exp

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_JS = os.path.join(RAIZ, "web_carga", "data.js")


def _catalogo_web():
    return {tipo: [c["clave"] for c in casillas if c["clave"] not in exp._SIN_FASTFIELD]
            for tipo, casillas in entrega.CATALOGO.items()}


def test_resistividades_no_se_pide_en_la_web():
    assert "resistividades" in exp._SIN_FASTFIELD
    assert "resistividades" not in _catalogo_web()["DCVG"]
    # pero sigue en el catálogo del paquete de entrega / procesamiento
    assert "resistividades" in [c["clave"] for c in entrega.CATALOGO["DCVG"]]


def test_data_js_esta_al_dia_con_el_catalogo():
    src = open(DATA_JS, encoding="utf-8").read()
    m = re.search(r"window\.CATALOGO = (\{.*?\});\n", src, re.S)
    assert m, "data.js sin window.CATALOGO"
    import json
    publicado = {t: [c["clave"] for c in cs] for t, cs in json.loads(m.group(1)).items()}
    assert publicado == _catalogo_web(), "regenera con python3 exportar_datos_carga.py"
