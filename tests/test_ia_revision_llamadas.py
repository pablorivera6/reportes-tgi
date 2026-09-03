"""Las llamadas a Claude, con un cliente falso: no se toca la red en los tests."""
import json

import pytest

import ia_revision


class _Bloque:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Respuesta:
    def __init__(self, payload):
        self.content = [_Bloque(json.dumps(payload, ensure_ascii=False))]
        self.stop_reason = "end_turn"


class _Mensajes:
    def __init__(self, payload):
        self._payload = payload
        self.ultima_llamada = None

    def create(self, **kwargs):
        self.ultima_llamada = kwargs
        return _Respuesta(self._payload)


class _ClienteFalso:
    def __init__(self, payload):
        self.messages = _Mensajes(payload)


def test_estructurar_nota_devuelve_observaciones_normalizadas():
    cli = _ClienteFalso({"observaciones": [
        {"categoria": "datos_generales", "campo": "info.tramo",
         "abscisa_ini": None, "abscisa_fin": None,
         "nota": "dice Cartago y es Ansermanuevo"},
        {"categoria": "texto_campo", "campo": "", "abscisa_ini": 12000,
         "abscisa_fin": 15000, "nota": "comentarios ilegibles"},
    ]})
    obs = ia_revision.estructurar_nota(
        "el tramo quedó como Cartago y del K12 al K15 los comentarios no se entienden",
        {"tramo": "Cartago", "tipo": "CIPS"}, cliente=cli)
    assert len(obs) == 2
    assert obs[0]["categoria"] == "datos_generales"
    assert obs[1]["abscisa_ini"] == 12000
    assert all(o["origen"] == "ia" for o in obs)


def test_estructurar_nota_usa_el_modelo_y_el_esquema():
    cli = _ClienteFalso({"observaciones": []})
    ia_revision.estructurar_nota("algo", {}, cliente=cli)
    kw = cli.messages.ultima_llamada
    assert kw["model"] == ia_revision.MODELO
    esquema = kw["output_config"]["format"]["schema"]
    assert esquema["properties"]["observaciones"]["items"]["properties"][
        "categoria"]["enum"] == list(ia_revision.CATEGORIAS_VALIDAS)


def test_estructurar_nota_con_categoria_inventada_falla_claro():
    cli = _ClienteFalso({"observaciones": [
        {"categoria": "inventada", "campo": "", "abscisa_ini": None,
         "abscisa_fin": None, "nota": "x"}]})
    with pytest.raises(ia_revision.IARevisionError):
        ia_revision.estructurar_nota("x", {}, cliente=cli)


def test_estructurar_nota_con_json_roto_falla_claro():
    class _Roto(_ClienteFalso):
        def __init__(self):
            super().__init__({})
            self.messages.create = lambda **kw: type(
                "R", (), {"content": [_Bloque("no soy json")],
                          "stop_reason": "end_turn"})()

    with pytest.raises(ia_revision.IARevisionError):
        ia_revision.estructurar_nota("x", {}, cliente=_Roto())
