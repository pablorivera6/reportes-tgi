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
