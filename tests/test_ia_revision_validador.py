"""La IA solo puede tocar metadatos y texto libre. Nunca datos de medición:
el informe se entrega a TGI bajo contrato y tiene que ser defendible."""
import ia_revision


def test_info_es_editable():
    assert ia_revision.ruta_editable("info.tramo") is True
    assert ia_revision.ruta_editable("info.ot") is True


def test_texto_de_una_fila_es_editable():
    assert ia_revision.ruta_editable("cips[12].observaciones") is True
    assert ia_revision.ruta_editable("hallazgos[0].descripcion") is True
    assert ia_revision.ruta_editable("dcvg_defectos[3].comentarios") is True


def test_datos_de_medicion_no_son_editables():
    for ruta in ("cips[12].off_mv", "cips[12].on_limpio", "cips[12].abscisa_val",
                 "dcvg_defectos[3].severidad_pct", "dcvg_defectos[3].ol_re",
                 "dcvg_defectos[3].p_re", "dcvg_defectos[3].clasificacion",
                 "cips[1].lat", "cips[1].lon", "potenciales[0].vac"):
        assert ia_revision.ruta_editable(ruta) is False, ruta


def test_rutas_raras_se_rechazan():
    for ruta in ("", None, "info", "cips.observaciones", "cips[].observaciones",
                 "__import__.os", "info.tramo; drop table"):
        assert ia_revision.ruta_editable(ruta) is False


def test_filtrar_separa_permitidos_de_descartados():
    cambios = [
        {"ruta": "info.tramo", "valor_antes": "Cartago",
         "valor_despues": "Ansermanuevo", "razon": "el revisor lo indicó"},
        {"ruta": "cips[5].off_mv", "valor_antes": -900, "valor_despues": -880,
         "razon": "se ve raro"},
    ]
    ok, fuera = ia_revision.filtrar_cambios(cambios)
    assert [c["ruta"] for c in ok] == ["info.tramo"]
    assert [c["ruta"] for c in fuera] == ["cips[5].off_mv"]


def test_aplicar_cambios_escribe_solo_lo_permitido():
    data = {"info": {"tramo": "Cartago"},
            "cips": [{"observaciones": "cruze", "off_mv": -900.0}]}
    n = ia_revision.aplicar_cambios(data, [
        {"ruta": "info.tramo", "valor_despues": "Ansermanuevo"},
        {"ruta": "cips[0].observaciones", "valor_despues": "cruce"},
        {"ruta": "cips[0].off_mv", "valor_despues": -1.0},
    ])
    assert n == 2
    assert data["info"]["tramo"] == "Ansermanuevo"
    assert data["cips"][0]["observaciones"] == "cruce"
    assert data["cips"][0]["off_mv"] == -900.0     # intacto


def test_aplicar_ignora_indices_fuera_de_rango():
    data = {"info": {}, "cips": [{"observaciones": "x"}]}
    assert ia_revision.aplicar_cambios(
        data, [{"ruta": "cips[99].observaciones", "valor_despues": "y"}]) == 0
