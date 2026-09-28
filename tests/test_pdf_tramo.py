"""PDF por TRAMO: todas las campañas del mismo tramo en paneles apilados.

Hasta ahora cada inspección generaba su propio PDF de tablero, con mapa, tablas
y muestras de lecturas: mucha información repetida y archivos pesados. Lo que
de verdad se lee de un tramo es su EVOLUCIÓN — DCVG 2026 sobre PAP 2026 sobre
CIPS 2024 sobre DCVG 2022— con todos los paneles compartiendo el mismo eje de
abscisas, para que una anomalía se pueda seguir en vertical entre campañas.

Por eso el rango del eje X se calcula UNA vez sobre todas las campañas: si cada
panel usara su propio rango, las columnas no coincidirían y el documento
mentiría visualmente.
"""
import pytest

import comparativa


def _detalle_cips():
    return {"inspeccion": {"tipo": "CIPS", "tramo": "San Pedro", "fecha": "2026-05-04"},
            "puntos": [{"abscisa": 0, "on_mv": -1500, "off_mv": -900,
                        "on_limpio": -1480, "off_limpio": -880},
                       {"abscisa": 1000, "on_mv": -1400, "off_mv": -820,
                        "on_limpio": -1390, "off_limpio": -830}]}


def _detalle_pap():
    return {"inspeccion": {"tipo": "PAP", "tramo": "San Pedro", "fecha": "2026-06-10"},
            "puntos": [{"abscisa": 200, "on_mv": -1300, "off_mv": -950},
                       {"abscisa": 900, "on_mv": -1250, "off_mv": -870}]}


def _detalle_dcvg():
    return {"inspeccion": {"tipo": "DCVG", "tramo": "San Pedro", "fecha": "2026-08-01"},
            "defectos": [{"abscisa": 300, "severidad_pct": 12.0, "clasificacion": "Muy Pequeño"},
                         {"abscisa": 1500, "severidad_pct": 44.0, "clasificacion": "Mediano"}]}


HIST_DCVG = {"tramo": "San Pedro", "tipo": "DCVG", "periodo": "Ago 2024",
             "puntos": [{"clase": "poste", "abscisa": 0, "on": -1200, "off": -900},
                        {"clase": "defecto", "abscisa": 500, "severidad_pct": 8.0,
                         "clasificacion": "Muy Pequeño"},
                        {"clase": "defecto", "abscisa": 2000, "severidad_pct": 20.0,
                         "clasificacion": "Pequeño"}]}

HIST_CIPS = {"tramo": "San Pedro", "tipo": "CIPS", "periodo": "Nov 2024",
             "puntos": [{"abscisa": 100, "on": -1600, "off": -1000},
                        {"abscisa": 2500, "on": -1550, "off": -950}]}


def _campanas():
    return comparativa.campanas_desde(
        {"CIPS": _detalle_cips(), "PAP": _detalle_pap(), "DCVG": _detalle_dcvg()},
        [HIST_DCVG, HIST_CIPS])


def test_normaliza_las_cinco_campanas():
    cs = _campanas()
    assert len(cs) == 5
    assert {c["tipo"] for c in cs} == {"CIPS", "PAP", "DCVG"}


def test_ordena_de_la_mas_reciente_a_la_mas_vieja():
    """Arriba lo de hoy, abajo lo viejo: así se lee la evolución hacia abajo."""
    etiquetas = [c["etiqueta"] for c in _campanas()]
    assert etiquetas[0].startswith("DCVG 2026")      # 2026-08-01, la más nueva
    assert etiquetas[-1].endswith("2024")            # las históricas al final
    anios = [c["anio"] for c in _campanas()]
    assert anios == sorted(anios, reverse=True)


def test_distingue_historico_de_actual():
    cs = _campanas()
    assert sum(1 for c in cs if c["origen"] == "actual") == 3
    assert sum(1 for c in cs if c["origen"] == "historico") == 2


def test_cips_usa_el_potencial_limpio_que_es_el_oficial_del_portal():
    """El portal publica `off_limpio`; el PDF no puede mostrar otro número."""
    c = next(c for c in _campanas() if c["tipo"] == "CIPS" and c["origen"] == "actual")
    assert [p["off"] for p in c["puntos"]] == [-880, -830]
    assert [p["on"] for p in c["puntos"]] == [-1480, -1390]


def test_del_dcvg_solo_entran_los_defectos_con_severidad():
    """En un histórico DCVG conviven postes y defectos; el panel grafica %IR."""
    c = next(c for c in _campanas() if c["tipo"] == "DCVG" and c["origen"] == "historico")
    assert len(c["puntos"]) == 2
    assert all(p.get("severidad_pct") is not None for p in c["puntos"])


def test_el_rango_de_abscisas_es_comun_a_todas_las_campanas():
    """Si cada panel usara su propio rango, las columnas no se alinearían."""
    ini, fin = comparativa.rango_abscisas(_campanas())
    assert ini == 0          # el CIPS actual arranca en 0
    assert fin == 2500       # el CIPS histórico llega a 2500


def test_rango_con_campanas_vacias_no_revienta():
    assert comparativa.rango_abscisas([{"puntos": []}]) == (0, 1)


def test_genera_un_pdf_con_el_tramo_y_todas_las_etiquetas():
    pypdf = pytest.importorskip("pypdf")
    import io
    b = comparativa.pdf_tramo("San Pedro", _campanas())
    assert b[:4] == b"%PDF"
    r = pypdf.PdfReader(io.BytesIO(b))
    txt = "\n".join(p.extract_text() or "" for p in r.pages)
    assert "San Pedro" in txt
    for c in _campanas():
        assert c["etiqueta"] in txt


def test_una_campana_sin_puntos_no_rompe_el_pdf():
    cs = _campanas()
    cs.append({"tipo": "PAP", "etiqueta": "PAP 2019", "anio": 2019,
               "origen": "historico", "puntos": []})
    b = comparativa.pdf_tramo("San Pedro", cs)
    assert b[:4] == b"%PDF"


def test_sin_campanas_avisa_en_vez_de_fallar():
    b = comparativa.pdf_tramo("San Pedro", [])
    assert b[:4] == b"%PDF"


def test_etiquetas_no_se_repiten_cuando_hay_dos_campanas_del_mismo_ano_y_tipo():
    """Dos DCVG del mismo año se distinguen por el mes, si no el lector no sabe
    cuál panel es cuál."""
    cs = comparativa.campanas_desde(
        {"DCVG": _detalle_dcvg()},
        [dict(HIST_DCVG, periodo="Mar 2026"), dict(HIST_DCVG, periodo="Sep 2026")])
    assert len({c["etiqueta"] for c in cs}) == len(cs)


# ── Campañas DCVG sin defectos ──────────────────────────────────────────────
# El 40 % de los paneles salía en blanco: una campaña DCVG que no encontró
# defectos no tenía nada que graficar, aunque hubiera medido decenas de postes
# con ON/OFF. "Sin defectos" es un RESULTADO, no una falta de datos, y el panel
# debe mostrar los potenciales que sí se midieron.
DET_DCVG_SIN_DEFECTOS = {
    "inspeccion": {"tipo": "DCVG", "tramo": "Zarzal", "fecha": "2026-07-30"},
    "defectos": [],
    "postes": [{"abscisa": 0, "on_mv": -1500, "off_mv": -950},
               {"abscisa": 600, "on_mv": -1450, "off_mv": -910}]}

HIST_DCVG_SIN_DEFECTOS = {
    "tramo": "Zarzal", "tipo": "DCVG", "periodo": "Jul 2024",
    "puntos": [{"clase": "poste", "abscisa": 100, "on": -1400, "off": -1000},
               {"clase": "poste", "abscisa": 5000, "on": -1380, "off": -980}]}


def test_campana_dcvg_sin_defectos_conserva_los_potenciales_de_sus_postes():
    cs = comparativa.campanas_desde({"DCVG": DET_DCVG_SIN_DEFECTOS},
                                    [HIST_DCVG_SIN_DEFECTOS])
    for c in cs:
        assert c["puntos"] == []          # no hubo defectos
        assert len(c["potenciales"]) == 2  # pero sí postes medidos


def test_una_campana_con_potenciales_no_cuenta_como_vacia():
    """Es lo que decidía si el panel decía 'sin datos'."""
    cs = comparativa.campanas_desde({"DCVG": DET_DCVG_SIN_DEFECTOS}, [])
    assert comparativa.tiene_datos(cs[0]) is True
    assert comparativa.tiene_datos({"puntos": [], "potenciales": []}) is False


def test_el_rango_de_abscisas_tiene_en_cuenta_los_postes():
    """Si el rango ignorara los potenciales, una campaña sin defectos quedaría
    fuera del eje común y su panel se dibujaría recortado."""
    cs = comparativa.campanas_desde({"DCVG": DET_DCVG_SIN_DEFECTOS},
                                    [HIST_DCVG_SIN_DEFECTOS])
    assert comparativa.rango_abscisas(cs) == (0, 5000)


def test_el_pdf_de_un_tramo_sin_defectos_no_queda_en_blanco():
    pypdf = pytest.importorskip("pypdf")
    import io
    cs = comparativa.campanas_desde({"DCVG": DET_DCVG_SIN_DEFECTOS},
                                    [HIST_DCVG_SIN_DEFECTOS])
    b = comparativa.pdf_tramo("Zarzal", cs)
    txt = "\n".join(p.extract_text() or ""
                    for p in pypdf.PdfReader(io.BytesIO(b)).pages)
    assert "sin datos" not in txt.lower()
    assert "Potencial" in txt          # se graficaron los postes


def test_etiqueta_sin_fecha_no_queda_como_guion_suelto():
    """La Dorada CIPS no tiene fecha: 'CIPS —' no le dice nada a nadie."""
    cs = comparativa.campanas_desde(
        {"CIPS": {"inspeccion": {"tipo": "CIPS", "tramo": "La Dorada"},
                  "puntos": [{"abscisa": 0, "on_mv": -1500, "off_mv": -900}]}}, [])
    assert cs[0]["etiqueta"] == "CIPS (sin fecha)"
