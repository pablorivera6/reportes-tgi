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
    # la tabla dice 'En validación': eso NO es un recubrimiento (ver abajo)
    assert d.get("tipo_recubrimiento") != "En validación"


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


# ── La OT del consolidado depende del PLAN (fila), no de la primera fila ─────
# `consolidado OT.xlsx` trae hasta tres filas por tramo: la del plan PAP
# ('INSP Y MTTO MENOR PREVENTIVO A URPC-PAP'), la del CIPS ('LEV PERFIL
# POTENCIALES PASO/PASO-CIPS') y la del DCVG ('INSP DE RECUBRIMIENTO
# DCVG/ACVG/PCM'), además de cupones, ánodos y calibración de cajas que no
# son inspecciones. Tomar siempre la primera ponía la OT equivocada.

@pytest.mark.parametrize("tramo,tipo,ot", [
    ("Ginebra", "CIPS", "1300011002"),
    ("Ginebra", "PAP", "1300015167"),               # 2026-Q2 ejecutada (control 2026)
    ("Obando - Tuluá", "CIPS", "1300010882"),
    ("Obando - Tuluá", "PAP", "1300014395"),        # 2026-Q1 ejecutada (control 2026)
    ("Termocentro", "DCVG", "1300012989"),          # no está en el control 2026: consolidado viejo
    ("Termocentro", "PAP", "1300011875"),
    ("Mariquita - Letras", "DCVG", "1300012991"),   # no la de calibración de cajas
    ("Jamundí", "CIPS", "1300011006"),
    ("Pradera", "CIPS", "1300010884"),
])
def test_ot_del_consolidado_segun_el_plan(tramo, tipo, ot):
    assert datos_tramo.info_de_ot(tramo, tipo).get("ot") == ot


# ── Control de OT 2026 de TGI (consolidado_ot_2026.csv) ──────────────────────
# El consolidado viejo trae las OT de 2025; el control de TGI de 2026 trae la
# OT de cada tramo por tipo (y a veces la de 2025 y la de 2026 del mismo
# tramo). Manda sobre el consolidado viejo; ot_por_tipo.csv sigue mandando
# sobre todo (es la corrección a mano).

@pytest.mark.parametrize("tramo,tipo,ot,distrito", [
    ("Ramal Marsella", "DCVG", "1300015004", "D07"),
    ("Ramal Marsella", "PAP", "1300014323", "D07"),
    ("Ansermanuevo", "CIPS", "1300014377", "D08"),     # no estaba en ninguna fuente
    ("Ramal Armenia", "PAP", "1300015146", "D07"),     # la de 2026, no la de 2025
    ("Ramal La Tebaida", "CIPS", "1300014341", "D07"), # TGI la llama 'TEBAIDA'
    ("Fresno", "DCVG", "1300015001", "D07"),           # TGI escribe 'FRESNO PK19+140'
    ("Loop - Ramal Armenia", "PAP", "1300015190", "D08"),
    ("Cartago", "DCVG", "1300015195", "D08"),          # igual en ot_por_tipo.csv
])
def test_ot_del_control_2026(tramo, tipo, ot, distrito):
    d = datos_tramo.info_de_ot(tramo, tipo)
    assert d.get("ot") == ot, d
    assert d.get("distrito") == distrito


def test_control_2026_no_pisa_la_ot_forzada_a_mano(monkeypatch):
    monkeypatch.setitem(datos_tramo._cache, 'ot_tipo',
                        [{"tipo": "DCVG", "tramo": "Marsella", "ot": "9999", "distrito": "D07", "plan": ""}])
    assert datos_tramo.info_de_ot("Ramal Marsella", "DCVG").get("ot") == "9999"


def test_mejor_ot_2026_prefiere_ejecutada_y_mas_reciente():
    filas = [{"ot": "a", "estado": "Por ejecutar", "trimestre": "2026-Q4"},
             {"ot": "b", "estado": "Ejecutada", "trimestre": "2025"},
             {"ot": "c", "estado": "Ejecutada", "trimestre": "2026-Q2"}]
    assert datos_tramo._mejor_ot_2026(filas)["ot"] == "c"
    assert datos_tramo._mejor_ot_2026(filas[:1])["ot"] == "a"


def test_pk_sin_espacio_se_recorta():
    assert mismo_tramo("FRESNO PK19+140", "Fresno")
    assert mismo_tramo("UBATE PK73+420", "Ubaté")
    assert mismo_tramo("PK 7+200 - PK 17+500", "PK 7+200 - PK 17+500")


def test_ot_nunca_es_la_de_cupones_ni_anodos():
    """Albania tiene una fila de cupones y una de inspección sin descripción:
    la de cupones no es una inspección de potenciales."""
    d = datos_tramo.info_de_ot("Albania", "PAP")
    assert d.get("ot") == "1300013515"
    assert d.get("ot") != "1300012814"


def test_sin_fila_del_plan_usa_la_del_tramo_sin_descripcion():
    """Villavicencio - Usme solo está en el bloque sin descripción del plan."""
    assert datos_tramo.info_de_ot("Villavicencio - Usme", "PAP").get("ot") == "1300013543"


# ── Contrato ─────────────────────────────────────────────────────────────────
# El FastField trae 'Cliente' = 'TGI' y eso se estaba escribiendo como número
# de contrato (y salía '_TGI_' en el nombre del archivo y del ZIP).

def test_autollenar_pone_el_contrato_de_tgi():
    d = datos_tramo.autollenar("Ramal Salento", "PAP")
    assert d.get("contrato") == datos_tramo.CONTRATO_TGI == "551007370"


def test_tramo_desconocido_no_inventa_contrato():
    assert "contrato" not in datos_tramo.autollenar("Ramal Que No Existe", "PAP")


# ── La casilla de OT (y cualquier otra) escrita a mano manda ─────────────────
# El autollenado se dispara al cargar archivos; si el usuario ya corrigió la OT
# en el generador, ese valor no se puede pisar.

def test_lo_escrito_a_mano_no_se_pisa():
    aplicar, manuales = datos_tramo.filtrar_autollenado(
        {"ot": "1300012786", "contrato": "551007370", "gasoducto": "Mariquita-Cali"},
        manuales={"ot"})
    assert "ot" not in aplicar
    assert aplicar == {"contrato": "551007370", "gasoducto": "Mariquita-Cali"}
    assert manuales == {"ot"}


def test_forzar_vuelve_a_automatico():
    aplicar, manuales = datos_tramo.filtrar_autollenado(
        {"ot": "1300012786"}, manuales={"ot", "fecha"}, forzar=True)
    assert aplicar == {"ot": "1300012786"}
    assert manuales == {"fecha"}          # lo que no se autollenó sigue manual


def test_sin_manuales_se_aplica_todo():
    aplicar, manuales = datos_tramo.filtrar_autollenado({"ot": "1"}, manuales=None)
    assert aplicar == {"ot": "1"} and manuales == set()


# ── Recubrimiento: 'En validación' no es un recubrimiento ────────────────────
# `Infraestrutura TGI.xlsx` tiene 'En validación' en los 39 ramales de
# Mariquita-Cali y el informe salía con eso como tipo de recubrimiento.

def test_en_validacion_no_se_autollena():
    # Obando sigue pendiente en recubrimiento_por_tramo.csv (su único histórico
    # dice 'No se conoce'): la tabla dice 'En validación' y eso no se escribe.
    d = datos_tramo.info_de_infraestructura("Obando")
    assert d.get("gasoducto") == "Mariquita-Cali"
    assert "tipo_recubrimiento" not in d


def test_los_ramales_confirmados_salen_fbe():
    # 2026-10-08: el ingeniero confirmó FBE para 38 ramales desde los históricos
    # TELMACOM / TECNA; ninguno debe salir 'En validación'.
    for tramo in ("Ramal Salento", "Ansermanuevo", "Pereira", "Zarzal", "La Virginia", "Tuluá"):
        d = datos_tramo.info_de_infraestructura(tramo)
        assert d.get("tipo_recubrimiento") == "FBE", tramo


def test_recubrimiento_real_de_la_tabla_sigue_saliendo():
    assert datos_tramo.info_de_infraestructura("Norean - San Alberto").get("tipo_recubrimiento") == "FBE"
    assert datos_tramo.info_de_infraestructura("María Conchita").get("tipo_recubrimiento") == "Tricapa"


def test_csv_de_recubrimientos_manda(monkeypatch):
    monkeypatch.setitem(datos_tramo._cache, 'recubrimiento', {"Salento": "FBE", "Pereira": "Tricapa"})
    assert datos_tramo.info_de_infraestructura("Ramal Salento").get("tipo_recubrimiento") == "FBE"
    assert datos_tramo.info_de_infraestructura("Pereira").get("tipo_recubrimiento") == "Tricapa"
    assert "tipo_recubrimiento" not in datos_tramo.info_de_infraestructura("Zarzal")


def test_csv_con_recubrimiento_vacio_es_solo_pendiente():
    """Una fila con el valor vacío (Obando) es solo un pendiente: no debe
    devolver '' ni 'En validación'. Las confirmadas devuelven su valor."""
    datos_tramo._cache.pop('recubrimiento', None)
    filas = datos_tramo._recubrimiento_por_tramo()
    assert all(v for v in filas.values())
    assert datos_tramo.recubrimiento_de("Obando", "En validación") is None
    assert datos_tramo.recubrimiento_de("Obando", "FBE") == "FBE"
    assert datos_tramo.recubrimiento_de("Salento", "En validación") == "FBE"
