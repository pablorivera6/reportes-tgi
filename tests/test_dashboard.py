"""Lógica del dashboard CIPS (KPIs y estado por punto)."""
from dashboard import estado_cp, resumen_cips, COLOR_ESTADO


def test_estado_cp():
    assert estado_cp(-1300) == "Sobreprotegido"
    assert estado_cp(-1200) == "Sobreprotegido"
    assert estado_cp(-1000) == "Protegido"
    assert estado_cp(-850) == "Protegido"
    assert estado_cp(-800) == "Desprotegido"
    assert estado_cp(None) == "Sin dato"
    assert estado_cp("") == "Sin dato"


def test_resumen_cips():
    cips = [
        {"abscisa_val": 0, "off_limpio": -900, "on_limpio": -1100, "lat": 4.6, "lon": -75.7},
        {"abscisa_val": 10, "off_limpio": -700, "on_limpio": -1000, "lat": 4.6, "lon": -75.7},
        {"abscisa_val": 20, "off_limpio": -1300, "on_limpio": -1500, "lat": 4.6, "lon": -75.7},
        {"abscisa_val": 30, "off_mv": None, "lat": None, "lon": None},   # sin dato
    ]
    r = resumen_cips(cips)
    assert r["total"] == 4
    assert r["con_dato"] == 3
    assert r["protegido"] == 1 and r["desprotegido"] == 1 and r["sobreprotegido"] == 1
    assert r["pct_protegido"] == round(100 / 3, 1)
    # color por estado y fallback off_mv
    prot = next(p for p in r["puntos"] if p["abscisa_val"] == 0)
    assert prot["estado"] == "Protegido" and prot["color"] == COLOR_ESTADO["Protegido"]


def test_resumen_usa_off_mv_si_no_hay_limpio():
    r = resumen_cips([{"abscisa_val": 0, "off_mv": -900, "lat": 4.6, "lon": -75.7}])
    assert r["puntos"][0]["off"] == -900 and r["puntos"][0]["estado"] == "Protegido"


def test_resumen_vacio():
    r = resumen_cips([])
    assert r["total"] == 0 and r["pct_protegido"] == 0.0
