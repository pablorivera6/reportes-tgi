"""DCVG: aviso de inspección visual pendiente. Cada interfase tierra-aire,
derivación o citygate del recorrido debe llevar su descripción de inspección
visual en las OBSERVACIONES del informe; la app solo avisa cuáles hay."""
from dcvg_reader import puntos_inspeccion_visual


def test_detecta_interfases_derivaciones_y_citygates():
    hall = [{"abscisa_val": 1200, "observaciones": "Cruce de vía"},
            {"abscisa_val": 2500, "observaciones": "Interfase tierra aire"},
            {"abscisa_val": 4000, "observaciones": "Derivación a EDS Buga"},
            {"abscisa_val": 7100, "observaciones": "City Gate Salento"},
            {"abscisa_val": 9000, "observaciones": "Inicio tramo aéreo"},
            {"abscisa_val": 9050, "observaciones": "Válvula"}]
    puntos = puntos_inspeccion_visual(hall)
    assert [a for a, _t in puntos] == [2500, 4000, 7100, 9000]


def test_tambien_mira_los_defectos_y_no_repite():
    hall = [{"abscisa_val": 2500, "observaciones": "interfase"},
            {"abscisa_val": 2500, "referencia": "Interfase"}]        # misma abscisa, mismo texto
    defectos = [{"pk_m": 3000, "comentarios": "defecto en la derivacion", "caracter": "AA"}]
    puntos = puntos_inspeccion_visual(hall, defectos)
    assert len(puntos) == 2 and puntos[1][0] == 3000


def test_sin_nada_que_avisar():
    assert puntos_inspeccion_visual([{"abscisa_val": 1, "observaciones": "Cruce"}]) == []
    assert puntos_inspeccion_visual([]) == []
