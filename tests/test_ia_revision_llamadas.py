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


DATA = {
    "info": {"tramo": "Cartago", "ot": "OT-9"},
    "cips": [{"abscisa_val": 12000, "observaciones": "cruze de bia", "off_mv": -900.0},
             {"abscisa_val": 13000, "observaciones": "balbula", "off_mv": -880.0},
             {"abscisa_val": 90000, "observaciones": "lejos", "off_mv": -870.0}],
}
OBS = [{"categoria": "texto_campo", "abscisa_ini": 12000, "abscisa_fin": 13000,
        "nota": "comentarios ilegibles"}]


def test_solo_manda_las_filas_de_las_abscisas_senaladas():
    cli = _ClienteFalso({"cambios": []})
    ia_revision.proponer_correcciones(OBS, DATA, "CIPS", cliente=cli)
    enviado = json.loads(cli.messages.ultima_llamada["messages"][0]["content"])
    absc = [f["abscisa_val"] for f in enviado["filas"]["cips"]]
    assert absc == [12000, 13000]      # la de 90000 no viaja


def test_descarta_las_propuestas_sobre_datos_de_medicion():
    cli = _ClienteFalso({"cambios": [
        {"ruta": "cips[0].observaciones", "valor_antes": "cruze de bia",
         "valor_despues": "cruce de vía", "razon": "ortografía"},
        {"ruta": "cips[0].off_mv", "valor_antes": -900.0, "valor_despues": -850.0,
         "razon": "parece fuera de rango"},
    ]})
    ok, fuera = ia_revision.proponer_correcciones(OBS, DATA, "CIPS", cliente=cli)
    assert [c["ruta"] for c in ok] == ["cips[0].observaciones"]
    assert [c["ruta"] for c in fuera] == ["cips[0].off_mv"]


def test_sin_abscisas_manda_una_muestra_acotada():
    cli = _ClienteFalso({"cambios": []})
    ia_revision.proponer_correcciones(
        [{"categoria": "datos_generales", "nota": "el tramo está mal"}],
        DATA, "CIPS", cliente=cli)
    enviado = json.loads(cli.messages.ultima_llamada["messages"][0]["content"])
    assert enviado["info"]["tramo"] == "Cartago"
    assert len(enviado["filas"].get("cips", [])) <= ia_revision.MAX_FILAS
