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
