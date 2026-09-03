"""Categorías de rechazo y a dónde enruta cada una."""
import pytest

import revision


def test_categorias_son_las_cuatro_acordadas():
    assert set(revision.CATEGORIAS) == {
        "datos_generales", "procesamiento", "texto_campo", "falta_info"}


def test_etiqueta_legible_de_cada_categoria():
    for cat in revision.CATEGORIAS:
        assert revision.etiqueta(cat)
        assert revision.etiqueta(cat) != cat        # es legible, no el slug


def test_normalizar_acepta_dict_parcial():
    obs = revision.normalizar({"categoria": "texto_campo", "nota": "  ilegible "})
    assert obs["categoria"] == "texto_campo"
    assert obs["nota"] == "ilegible"
    assert obs["estado"] == "abierta" and obs["origen"] == "revisor"
    assert obs["abscisa_ini"] is None and obs["campo"] is None


def test_normalizar_rechaza_categoria_invalida():
    with pytest.raises(ValueError):
        revision.normalizar({"categoria": "lo_que_sea", "nota": "x"})


def test_normalizar_convierte_abscisas_a_entero():
    obs = revision.normalizar({"categoria": "procesamiento",
                               "abscisa_ini": "1200.6", "abscisa_fin": ""})
    assert obs["abscisa_ini"] == 1201 and obs["abscisa_fin"] is None


def test_requiere_crudos_solo_para_procesamiento():
    assert revision.requiere_crudos([{"categoria": "procesamiento"}]) is True
    assert revision.requiere_crudos([{"categoria": "texto_campo"},
                                     {"categoria": "datos_generales"}]) is False


def test_falta_info_no_vuelve_al_generador():
    assert revision.es_para_tecnico({"categoria": "falta_info"}) is True
    assert revision.es_para_tecnico({"categoria": "texto_campo"}) is False
