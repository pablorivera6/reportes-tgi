"""Lectura de un informe DCVG YA GENERADO, para publicarlo al portal.

Los informes que se hicieron antes del portal (o fuera de la app) solo existen
como .xlsx. Este lector los devuelve en la MISMA forma que produce el generador
(`pk_m`, `on`, `ol_re`…), que es la que `db.guardar_inspeccion_dcvg` espera, de
modo que publicarlos pase por el mismo camino que una inspección recién
procesada — incluido el recálculo de severidad en `db._severidad_dcvg`.

La hoja se lee por ETIQUETA de encabezado (igual que los históricos): la
plantilla de PCC parte el %IR en tres columnas AA/CA/CC y la del contratista lo
pone en una sola.
"""
import openpyxl
import pytest

from informe_dcvg import leer_informe_dcvg


def _informe(tmp_path, nombre="informe.xlsx"):
    wb = openpyxl.Workbook()

    # ── hoja Informe (metadata: etiqueta en A/R/AA, valor en G/U/AE) ────────
    ws = wb.active
    ws.title = "Informe"
    ws["A6"], ws["G6"] = "Fecha", "29/05/2026 A 09/06/2026"
    ws["R6"], ws["U6"] = "Serial equipo", "6697"
    ws["AA6"], ws["AE6"] = "No de contrato", "551007370"
    ws["A7"], ws["G7"] = "Gasoducto", "Mariquita-Cali"
    ws["R7"], ws["U7"] = "Fecha calibración Eqp", "2026-02-05"
    ws["AA7"], ws["AE7"] = "Contratista", "PCC"
    ws["A8"], ws["G8"] = "Tramo", "Neira"
    ws["R8"], ws["U8"] = "Tipo de recubrimiento", "FBE"
    ws["AA8"], ws["AE8"] = "OT", "1300014995"
    ws["A9"], ws["G9"] = "Inspector", "Evelio Alvarez"
    ws["R9"], ws["U9"] = "Diámetro", "2 in"
    ws["AA9"], ws["AE9"] = "Ciclo", "1.6 ON -0.4 OFF"

    # ── hoja Inspección DCVG (postes + defectos + hallazgos intercalados) ───
    d = wb.create_sheet("Inspección DCVG")
    for col, txt in [("A6", "ÍTEM"), ("B6", "REFERENCIAS GEOGRÁFICAS"),
                     ("C6", "DISTANCIA TRAMO\n[m]"), ("D6", "ABSCISA"),
                     ("E6", "LATITUD"), ("F6", "LONGITUD"), ("G6", "ALTITUD\n[msnm]"),
                     ("H6", "FORMA [mV]"), ("L6", "CARÁCTER"), ("M6", "OL/RE\n[mV]"),
                     ("N6", "POTENCIAL ESTRUCTURA-SUELO [mV]"), ("P6", "PULSO\n[mV]"),
                     ("Q6", "P/RE\n[mV] "), ("R6", "PROFUNDIDAD [cm]"),
                     ("S6", "SEVERIDAD [%IR]"), ("V6", "SEVERIDAD [CLASIFICACIÓN]"),
                     ("W6", "RESISTIVIDAD [Ohm-cm]"), ("X6", "OBSERVACIONES")]:
        d[col] = txt
    d["N7"], d["O7"] = "ON", "OFF"
    d["S7"], d["T7"], d["U7"] = "AA", "CA", "CC"
    # poste (tiene ON/OFF)
    d["A8"], d["B8"], d["D8"] = 1, "Poste de potencial", 0
    d["E8"], d["F8"] = 5.037368, -75.4472726
    d["N8"], d["O8"], d["P8"] = -1225, -1101, 124
    d["X8"] = "Poste de potencial"
    # hallazgo intercalado: ni poste ni defecto (va en su propia hoja)
    d["A9"], d["B9"], d["D9"] = 2, "Cruce de via ", 250
    d["E9"], d["F9"] = 5.0388, -75.4480
    d["X9"] = "Cruce de via"
    # defecto
    d["A10"], d["B10"], d["D10"] = 3, "Defecto", 2110
    d["E10"], d["F10"] = 5.0524768, -75.4496803
    d["H10"], d["I10"], d["J10"], d["K10"] = 40.2, 45.8, 38.8, 43.7   # N,E,S,O
    d["L10"], d["M10"] = "CC", 47
    d["Q10"], d["R10"] = 377.52, 185
    d["U10"], d["V10"] = 0.12449, "Muy Pequeño"
    d["X10"] = "Defecto"
    # Segundo poste. Su pulso (724.76) está elegido para que la interpolación
    # entre los dos postes dé en la abscisa 2110 el mismo P/RE = 377.52 que
    # trae el informe: así el test compara peras con peras.
    d["A11"], d["B11"], d["D11"] = 4, "Poste de potencial", 5000
    d["N11"], d["O11"], d["P11"] = -2176, -1451.24, 724.76
    d["A13"], d["B13"] = None, "ELABORÓ"          # bloque de firmas

    # ── hoja Resistividad (A absc · B sector · C/D coords · E prof · F/H/J R)
    r = wb.create_sheet("Resistividad")
    r["A7"], r["B7"], r["C7"] = "ABSCISADO", "DESCRIPCIÓN", "GEORREFERENCIACIÓN"
    r["C8"], r["D8"], r["E8"] = "Latitud ", "Longitud", "Profundidad"
    r["F8"], r["G8"], r["H8"], r["I8"], r["J8"], r["K8"] = ("S1 =", "1 m", "S2 =",
                                                            "2 m", "S3=", "3 m")
    r["A9"], r["B9"] = 0, "Poste"
    r["C9"], r["D9"], r["E9"] = 5.0373723, -75.4472841, 150
    r["F9"], r["H9"], r["J9"] = 71, 37, 29
    r["A10"], r["B10"] = 250, "Potrero"
    r["C10"], r["D10"], r["E10"] = 5.0391222, -75.4472825, 160
    r["F10"], r["H10"], r["J10"] = 45, 32, 17

    # ── hoja Hallazgos (encabezado fila 11, datos desde la 12) ──────────────
    h = wb.create_sheet("Hallazgos")
    for col, txt in [("A11", "ÍTEM"), ("B11", "ABSCISA INICIO"),
                     ("C11", "ABSCISA FIN"), ("D11", "LONGITUD [m]"),
                     ("E11", "GASODUCTO"), ("F11", "TRAMO"), ("G11", "LATITUD INICIO"),
                     ("H11", "LONGITUD INICIO"), ("I11", "LATITUD FIN"),
                     ("J11", "LONGITUD FIN"), ("K11", "FECHA"),
                     ("L11", "TIPO DE HALLAZGO"), ("M11", "DESCRIPCIÓN DEL HALLAZGO")]:
        h[col] = txt
    h["A12"], h["B12"], h["C12"], h["D12"] = 1, 700, 701, 1
    h["E12"], h["F12"] = "Mariquita-Cali", "Neira"
    h["G12"], h["H12"] = 5.04221583, -75.4505825
    h["I12"], h["J12"] = 5.04221583, -75.4505825
    h["K12"], h["L12"], h["M12"] = "2026-06-08", "Linea AT", "Linea AT"
    h["A13"], h["B13"], h["C13"] = 2, 3050, 3052
    h["L13"], h["M13"] = "Linea BT", "Linea BT"

    ruta = str(tmp_path / nombre)
    wb.save(ruta)
    return ruta


def test_metadata_del_informe(tmp_path):
    info = leer_informe_dcvg(_informe(tmp_path))["info"]
    assert info["tramo"] == "Neira"
    assert info["ot"] == "1300014995"
    assert info["contrato"] == "551007370"
    assert info["gasoducto"] == "Mariquita-Cali"
    assert info["inspector"] == "Evelio Alvarez"
    assert info["contratista"] == "PCC"
    assert info["serial_equipo"] == "6697"
    assert info["tipo_recubrimiento"] == "FBE"
    assert info["diametro"] == "2 in"
    assert "29/05/2026" in info["fecha"]


def test_separa_postes_de_defectos_y_descarta_los_hallazgos_intercalados(tmp_path):
    """La hoja mezcla postes, defectos y hallazgos; los hallazgos tienen su
    propia hoja, así que aquí solo deben salir postes y defectos."""
    r = leer_informe_dcvg(_informe(tmp_path))
    assert len(r["postes"]) == 2
    assert len(r["defectos"]) == 1
    assert all(p["pk_m"] != 250 for p in r["postes"] + r["defectos"])


def test_campos_del_poste(tmp_path):
    p = leer_informe_dcvg(_informe(tmp_path))["postes"][0]
    assert p["pk_m"] == 0
    assert p["on"] == -1225 and p["off"] == -1101
    assert p["tipo"] == "Poste de potencial"
    assert round(p["lat"], 5) == 5.03737


def test_campos_del_defecto_incluida_la_forma_por_horas(tmp_path):
    """Forma [mV]: N->H(12h), E->I(3h), S->J(6h), O->K(9h)."""
    d = leer_informe_dcvg(_informe(tmp_path))["defectos"][0]
    assert d["pk_m"] == 2110
    assert d["caracter"] == "CC"
    assert d["ol_re"] == 47
    assert (d["forma_n"], d["forma_e"], d["forma_s"], d["forma_o"]) == (
        40.2, 45.8, 38.8, 43.7)
    assert d["profundidad"] == 185


def test_resistividades(tmp_path):
    rs = leer_informe_dcvg(_informe(tmp_path))["resistividades"]
    assert len(rs) == 2
    assert rs[0]["pk_m"] == 0 and rs[0]["sector"] == "Poste"
    assert (rs[0]["r1"], rs[0]["r2"], rs[0]["r3"]) == (71, 37, 29)
    assert rs[0]["profundidad"] == 150


def test_hallazgos_salen_de_su_propia_hoja(tmp_path):
    hs = leer_informe_dcvg(_informe(tmp_path))["hallazgos"]
    assert len(hs) == 2
    assert hs[0]["abscisa_inicio"] == 700 and hs[0]["abscisa_fin"] == 701
    assert hs[0]["tipo"] == "Linea AT"
    assert round(hs[0]["lat_inicio"], 5) == 5.04222


def test_no_pasa_del_bloque_de_firmas(tmp_path):
    r = leer_informe_dcvg(_informe(tmp_path))
    assert len(r["postes"]) + len(r["defectos"]) == 3


def test_la_severidad_recalculada_coincide_con_la_del_informe(tmp_path):
    """El portal NO guarda el %IR del Excel: lo recalcula `db._severidad_dcvg`.
    Si los dos no coinciden, el tablero mostraría números distintos al informe
    ya entregado al cliente."""
    import db
    r = leer_informe_dcvg(_informe(tmp_path))
    sev = db._severidad_dcvg(r["postes"], r["defectos"])
    # P/RE interpolado entre los postes con pulso == el Q del Excel
    assert sev[0]["p_re"] == pytest.approx(377.52, abs=0.1)
    # el informe trae la fracción (0.12449); el portal usa % (12.449)
    assert sev[0]["severidad_pct"] == pytest.approx(12.45, abs=0.05)
    assert sev[0]["clasificacion"] == "Muy Pequeño"


def test_lee_la_severidad_que_trae_el_informe(tmp_path):
    """Un informe entregado es el documento oficial: sus P/RE y %IR mandan
    sobre cualquier recálculo."""
    d = leer_informe_dcvg(_informe(tmp_path))["defectos"][0]
    assert d["p_re"] == pytest.approx(377.52, abs=0.01)
    assert d["severidad_pct"] == pytest.approx(12.45, abs=0.01)   # 0.12449 -> %
    assert d["clasificacion"] == "Muy Pequeño"


def test_severidades_del_informe_tiene_la_forma_que_espera_db(tmp_path):
    from informe_dcvg import severidades_del_informe
    r = leer_informe_dcvg(_informe(tmp_path))
    sev = severidades_del_informe(r["defectos"])
    assert len(sev) == len(r["defectos"])
    assert set(sev[0]) == {"p_re", "severidad_pct", "clasificacion"}
    assert sev[0]["clasificacion"] == "Muy Pequeño"
