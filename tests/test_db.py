"""Helpers puros de db.py y comportamiento sin credenciales Supabase."""
import pytest

import db


def test_f_i_conversion():
    assert db._f("−") is None or db._f("x") is None   # texto no numérico -> None
    assert db._f(None) is None and db._f("") is None
    assert db._f("12.5") == 12.5 and db._f(-3) == -3.0
    assert db._i(19.6) == 20 and db._i(None) is None


def test_fecha_normaliza():
    assert db._fecha("2026-07-15 00:00:00") == "2026-07-15"
    assert db._fecha("2026-07-15") == "2026-07-15"
    assert db._fecha(None) is None and db._fecha("nan") is None


def test_disponible_sin_secrets(monkeypatch):
    monkeypatch.setattr(db, "_secrets", lambda: {})
    assert db.disponible() is False
    assert db.disponible(write=True) is False


def test_guardar_sin_config_lanza_error(monkeypatch):
    monkeypatch.setattr(db, "_secrets", lambda: {})
    with pytest.raises(RuntimeError):
        db.guardar_inspeccion_cips({}, [], [])
    with pytest.raises(RuntimeError):
        db.guardar_inspeccion_pap({}, [], [])
    with pytest.raises(RuntimeError):
        db.guardar_inspeccion_dcvg({}, [], [], [], [])


def test_severidad_dcvg_interpola_pre_y_clasifica():
    # postes con pulso en 0 (P=200) y 100 (P=400); defecto en 50 -> P/RE=300
    postes = [{"pk_m": 0, "on": -1500, "off": -1300},
              {"pk_m": 100, "on": -1600, "off": -1200}]
    defectos = [{"pk_m": 50, "ol_re": 60, "caracter": "AA"},    # 20% -> Pequeño
                {"pk_m": 50, "ol_re": 30, "caracter": "AA"},    # 10% -> Muy Pequeño
                {"pk_m": 50, "ol_re": 240, "caracter": "AA"}]   # 80% -> Grande
    sev = db._severidad_dcvg(postes, defectos)
    assert sev[0]["p_re"] == 300.0
    assert sev[0]["severidad_pct"] == 20.0 and sev[0]["clasificacion"] == "Pequeño"
    assert sev[1]["clasificacion"] == "Muy Pequeño"
    assert sev[2]["clasificacion"] == "Grande"


def test_severidad_dcvg_sin_postes_no_rompe():
    sev = db._severidad_dcvg([], [{"pk_m": 10, "ol_re": 50, "caracter": "AA"}])
    assert sev[0]["p_re"] is None and sev[0]["severidad_pct"] is None
