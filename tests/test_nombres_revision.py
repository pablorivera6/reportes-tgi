"""El entregable corregido no puede llamarse Rev.A igual que el rechazado."""
import nombres


INFO = {"tipo_inspeccion": "DCVG", "tramo": "Salento", "fecha": "2026-03-15",
        "ot": "1300013506", "contrato": "551007370", "tipo_ducto": "Ramal"}


def test_por_defecto_sigue_siendo_rev_a():
    assert nombres.nombre_archivo(INFO).endswith("_PCC_Rev.A.xlsx")


def test_revision_b_cambia_el_sufijo():
    assert nombres.nombre_archivo(INFO, revision="B").endswith("_PCC_Rev.B.xlsx")


def test_el_resto_del_nombre_no_cambia():
    a = nombres.nombre_archivo(INFO)
    b = nombres.nombre_archivo(INFO, revision="B")
    assert a.replace("Rev.A", "Rev.B") == b


def test_siguiente_revision_avanza_la_letra():
    assert nombres.siguiente_revision("A") == "B"
    assert nombres.siguiente_revision("B") == "C"
    assert nombres.siguiente_revision(None) == "B"    # sin dato: ya hubo una
    assert nombres.siguiente_revision("Z") == "Z"     # tope, no da la vuelta
