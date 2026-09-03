"""El mapeador inverso BD→generador. Si esto se desincroniza, el informe
corregido sale con datos corridos y NADIE se entera: no revienta."""
import db
import revision


CIPS_ORIG = [{
    "abscisa_val": 1200, "fecha": "2026-03-04",
    "on_mv": -1500.0, "off_mv": -900.0,
    "on_limpio": -1490.0, "off_limpio": -905.0,
    "natural_mv": -600.0, "polarizacion_mv": -305.0, "vac_mv": 2.5,
    "metal_on": -1.1, "metal_off": -0.9,
    "far_on": -1.2, "far_off": -0.95,
    "near_on": -1.05, "near_off": -0.9,
    "ir_on_off": 595.0, "lat": 4.1, "lon": -75.2,
    "observaciones": "cruce de via",
}]


def test_cips_round_trip_conserva_todas_las_claves():
    filas = db._puntos_cips_filas("insp-1", CIPS_ORIG)
    vuelta = revision.cips_desde_filas(filas)
    assert len(vuelta) == 1
    for k, v in CIPS_ORIG[0].items():
        assert vuelta[0][k] == v, f"se perdio o cambio '{k}'"


def test_cips_no_devuelve_columnas_de_bd_ni_derivados():
    filas = db._puntos_cips_filas("insp-1", CIPS_ORIG)
    vuelta = revision.cips_desde_filas(filas)
    for prohibido in ("inspeccion_id", "item", "estado", "abscisa",
                      "lejano_on", "cercano_on"):
        assert prohibido not in vuelta[0]


PAP_ORIG = [{
    "abscisa": 800, "fecha": "2026-03-05", "on_mv": -1400.0, "off_mv": -880.0,
    "potencial_natural": -550.0, "polarizacion": -330.0, "vac": 1.8,
    "ir_on_off": 520.0, "resistencia": 12.0, "lat": 4.2, "lon": -75.3,
    "ref_geografica": "poste K0+800", "observaciones": "tapa suelta",
}]

POSTES_ORIG = [{
    "pk_m": 0, "tipo": "Poste", "on": -1500.0, "off": -1300.0, "vac": 2.0,
    "resistencia": 8.0, "lat": 4.0, "lon": -75.0,
}, {
    "pk_m": 100, "tipo": "Poste", "on": -1600.0, "off": -1200.0, "vac": 2.1,
    "resistencia": 9.0, "lat": 4.01, "lon": -75.01,
}]

DEFECTOS_ORIG = [{
    "pk_m": 50, "sector": "A", "forma_n": 12.0, "forma_e": 3.0,
    "forma_s": 6.0, "forma_o": 9.0, "caracter": "AA", "ol_re": 60.0,
    "profundidad": 1.2, "posicion_reloj": "6", "lat": 4.005, "lon": -75.005,
    "comentarios": "defecto en soldadura",
}]

RESIST_ORIG = [{
    "pk_m": 300, "sector": "B", "profundidad": 1.0,
    "r1": 10.0, "r2": 20.0, "r3": 30.0, "lat": 4.02, "lon": -75.02,
}]

HALLAZGOS_ORIG = [{
    "abscisa_val": 1500, "abscisa_fin": 1700, "longitud": 200.0,
    "lat": 4.03, "lon": -75.03, "lat_fin": 4.04, "lon_fin": -75.04,
    "fecha": "2026-03-06", "tipo": "Cruce", "descripcion": "cruce de vía",
}]


def test_pap_round_trip():
    vuelta = revision.pap_desde_filas(db._puntos_pap_filas("i", PAP_ORIG))
    for k, v in PAP_ORIG[0].items():
        assert vuelta[0][k] == v, f"se perdio o cambio '{k}'"


def test_postes_round_trip():
    vuelta = revision.postes_desde_filas(db._postes_dcvg_filas("i", POSTES_ORIG))
    for k, v in POSTES_ORIG[0].items():
        assert vuelta[0][k] == v, f"se perdio o cambio '{k}'"


def test_defectos_round_trip_sin_derivados():
    sev = db._severidad_dcvg(POSTES_ORIG, DEFECTOS_ORIG)
    filas = db._defectos_dcvg_filas("i", DEFECTOS_ORIG, sev)
    assert filas[0]["severidad_pct"] is not None       # la BD sí los guarda
    vuelta = revision.defectos_desde_filas(filas)
    for k, v in DEFECTOS_ORIG[0].items():
        assert vuelta[0][k] == v, f"se perdio o cambio '{k}'"
    for derivado in ("p_re", "severidad_pct", "clasificacion"):
        assert derivado not in vuelta[0], f"'{derivado}' es derivado, no se rehidrata"


def test_resistividades_round_trip():
    vuelta = revision.resist_desde_filas(db._resist_dcvg_filas("i", RESIST_ORIG))
    for k, v in RESIST_ORIG[0].items():
        assert vuelta[0][k] == v, f"se perdio o cambio '{k}'"


def test_hallazgos_round_trip():
    vuelta = revision.hallazgos_desde_filas(db._hallazgos_filas("i", HALLAZGOS_ORIG))
    for k, v in HALLAZGOS_ORIG[0].items():
        assert vuelta[0][k] == v, f"se perdio o cambio '{k}'"


DETALLE_CIPS = {
    "inspeccion": {
        "id": "insp-1", "tipo": "CIPS", "tramo": "Ansermanuevo",
        "fecha": "2026-03-04", "inspector": "Juan Perez", "ot": "OT-9",
        "contexto": {"info": {"tramo": "Ansermanuevo", "contrato": "551007370",
                              "tipo_ducto": "Ramal", "distrito": "7"}},
    },
    "puntos": [], "hallazgos": [], "tramos": [],
}


def test_rehidratar_prefiere_el_contexto_y_completa_con_la_fila():
    out = revision.rehidratar(DETALLE_CIPS, "CIPS")
    # del contexto (la fila `inspecciones` no guarda estos)
    assert out["info"]["contrato"] == "551007370"
    assert out["info"]["tipo_ducto"] == "Ramal"
    # de la fila (el contexto no los traía)
    assert out["info"]["inspector"] == "Juan Perez"
    assert out["info"]["ot"] == "OT-9"
    assert out["info"]["tipo_inspeccion"] == "CIPS"


def test_rehidratar_cips_devuelve_las_claves_del_tipo():
    detalle = dict(DETALLE_CIPS, puntos=db._puntos_cips_filas("i", CIPS_ORIG))
    out = revision.rehidratar(detalle, "CIPS")
    assert out["cips"][0]["abscisa_val"] == 1200
    assert "dcvg_postes" not in out and "potenciales" not in out


def test_rehidratar_dcvg_devuelve_las_cuatro_listas():
    sev = db._severidad_dcvg(POSTES_ORIG, DEFECTOS_ORIG)
    detalle = {
        "inspeccion": {"id": "i", "tipo": "DCVG", "tramo": "Salento"},
        "postes": db._postes_dcvg_filas("i", POSTES_ORIG),
        "defectos": db._defectos_dcvg_filas("i", DEFECTOS_ORIG, sev),
        "resistividades": db._resist_dcvg_filas("i", RESIST_ORIG),
        "hallazgos": db._hallazgos_filas("i", HALLAZGOS_ORIG),
    }
    out = revision.rehidratar(detalle, "DCVG")
    assert out["dcvg_postes"][0]["pk_m"] == 0
    assert out["dcvg_defectos"][0]["ol_re"] == 60.0
    assert out["dcvg_resist"][0]["r2"] == 20.0
    assert out["dcvg_hallazgos"][0]["descripcion"] == "cruce de vía"
