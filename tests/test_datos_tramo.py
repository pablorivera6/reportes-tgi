"""Autollenado de Datos Generales a partir del nombre del tramo.

Dos problemas que resuelve:

1. **El nombre no coincide entre archivos.** FastField manda "Ramal
   Ansermanuevo"; `Infraestrutura TGI.xlsx` dice "Ansermanuevo" y
   `consolidado OT.xlsx` dice "Salento  PK 15+921". La búsqueda anterior exigía
   que el archivo *contuviera* el texto tal cual, así que con el prefijo
   "Ramal" no encontraba nada y Gasoducto/Diámetro/Recubrimiento/Tipo Ducto
   quedaban vacíos.

2. **La OT dependía del tipo de inspección.** `consolidado OT.xlsx` trae la OT
   del plan de potenciales (INT-CE M.POT). Para un DCVG esa OT es la de otro
   plan: el informe salía con la OT equivocada. Las OT por plan están en
   `ot_por_tipo.csv`.
"""
import pytest

from nombres import limpiar_tramo, mismo_tramo
import datos_tramo


# ── Comparación de nombres ───────────────────────────────────────────────────

@pytest.mark.parametrize("escrito,archivo", [
    ("Ramal Ansermanuevo", "Ansermanuevo"),
    ("Ansermanuevo", "Ramal Ansermanuevo"),
    ("Salento", "Salento  PK 15+921"),
    ("Ramal Salento", "Salento  PK 15+921 D07"),
    ("La Unión", "La Unión  (9+217) "),
    ("LA VICTORIA", "La Victoria  (3+032)"),
    ("Troncal Andalucía", "ANDALUCÍA PK 250+165 D08"),
    ("Chinchiná", "chinchina"),
])
def test_reconoce_el_mismo_tramo(escrito, archivo):
    assert mismo_tramo(escrito, archivo), f"{escrito!r} debería casar con {archivo!r}"


@pytest.mark.parametrize("a,b", [
    ("Buga", "Bugalagrande"),          # el caso peligroso: uno es prefijo del otro
    ("Salento", "San Pedro"),
    ("La Victoria", "La Unión"),
    ("Pradera", "Pradera Loop"),       # nombres distintos, no se confunden
])
def test_no_confunde_tramos_distintos(a, b):
    assert not mismo_tramo(a, b), f"{a!r} NO debería casar con {b!r}"


def test_limpia_prefijo_pk_y_distrito():
    assert limpiar_tramo("Ramal Salento  PK 15+921 D07") == "salento"
    assert limpiar_tramo("Troncal La Unión (9+217) D08") == "la union"
    # un tramo que SE LLAMA 'PK 7+200 - PK 17+500' no se puede vaciar
    assert limpiar_tramo("PK 7+200 - PK 17+500")


# ── Infraestructura ──────────────────────────────────────────────────────────

def test_infraestructura_con_prefijo_ramal():
    """El caso real que falló: FastField manda 'Ramal Ansermanuevo'."""
    d = datos_tramo.info_de_infraestructura("Ramal Ansermanuevo")
    assert d.get("gasoducto") == "Mariquita-Cali"
    assert d.get("tipo_ducto") == "Ramal"
    assert d.get("diametro")
    assert d.get("tipo_recubrimiento")


def test_infraestructura_sin_prefijo_sigue_funcionando():
    assert datos_tramo.info_de_infraestructura("Ansermanuevo").get("gasoducto") \
        == "Mariquita-Cali"


def test_tramo_inexistente_no_inventa():
    assert datos_tramo.info_de_infraestructura("Ramal Que No Existe") == {}


# ── Órdenes de trabajo ───────────────────────────────────────────────────────

def test_ot_de_dcvg_no_es_la_de_potenciales():
    """Salento: 1300012786 es la del plan de potenciales; la del DCVG es otra."""
    dcvg = datos_tramo.info_de_ot("Ramal Salento", "DCVG")
    assert dcvg["ot"] == "1300016109"
    pap = datos_tramo.info_de_ot("Ramal Salento", "PAP")
    assert pap["ot"] == "1300012786"
    assert dcvg["ot"] != pap["ot"]


def test_ot_trae_distrito_y_longitud():
    d = datos_tramo.info_de_ot("Salento", "DCVG")
    assert d.get("distrito") == "D07"
    assert d.get("longitud_km") == pytest.approx(15.774, abs=0.01)


def test_ot_sin_tipo_usa_el_consolidado():
    assert datos_tramo.info_de_ot("Salento").get("ot") == "1300012786"


def test_ot_de_un_tramo_que_solo_esta_en_el_csv():
    """Cartago no está en consolidado OT.xlsx; sí en ot_por_tipo.csv."""
    d = datos_tramo.info_de_ot("Cartago", "DCVG")
    assert d.get("ot") == "1300015195"


def test_ot_de_tramo_desconocido():
    assert datos_tramo.info_de_ot("Ramal Que No Existe", "DCVG") == {}


def test_todas_las_ot_del_csv_se_encuentran():
    """Cada fila del CSV debe ser localizable por su nombre de tramo."""
    filas = datos_tramo._ot_por_tipo()
    assert len(filas) >= 14
    for f in filas:
        d = datos_tramo.info_de_ot(f["tramo"], f["tipo"] or "DCVG")
        assert d.get("ot") == f["ot"], f"no se encontró la OT de {f['tramo']}"


def test_prefijos_encadenados_y_nombres_raros():
    """Casos reales del archivo: tramos que se llaman 'PK 7+200 - PK 17+500' o
    'Gasoducto del Ariari'."""
    assert mismo_tramo("Ramal Gasoducto del Ariari", "Gasoducto del Ariari")
    assert mismo_tramo("Ramal Troncal Cusiana - Miraflores", "Troncal Cusiana - Miraflores")
    assert mismo_tramo("PK 7+200 - PK 17+500", "PK 7+200 - PK 17+500")
    assert not mismo_tramo("Ramal", "Salento")
    assert not mismo_tramo("", "Salento")


def test_no_confunde_un_ramal_con_su_loop():
    """'La Belleza - Vasconia' está como Troncal (VRMB) y como LOOP (BEVV)."""
    d = datos_tramo.info_de_infraestructura("La Belleza - Vasconia")
    assert d.get("tipo_ducto", "").lower() != "loop"
