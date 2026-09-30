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


@pytest.mark.parametrize("entrada", [
    "20/09/2026", "20/09/2026 08:15:00", "20-09-2026", "2026/09/20",
    "2026-09-20T08:15:00",
])
def test_fecha_dia_mes_anio_a_iso(entrada):
    # Supabase rechaza '20/09/2026' (date/time field value out of range).
    assert db._fecha(entrada) == "2026-09-20"


def test_fecha_objetos_y_basura():
    import datetime as dt
    import pandas as pd
    assert db._fecha(dt.date(2026, 9, 20)) == "2026-09-20"
    assert db._fecha(dt.datetime(2026, 9, 20, 8, 15)) == "2026-09-20"
    assert db._fecha(pd.Timestamp("2026-09-20 08:15")) == "2026-09-20"
    assert db._fecha("sin fecha") is None      # nunca mandar texto inválido
    assert db._fecha("31/02/2026") is None


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


class _Resp:
    def __init__(self, data):
        self.data = data


class _Q:
    """Imita al query builder de supabase: devuelve como máximo 1000 filas
    por consulta, como el servidor real."""
    TOPE = 1000

    def __init__(self, filas):
        self.filas, self.desde, self.hasta = filas, 0, None

    def select(self, *a, **k): return self
    def eq(self, *a, **k): return self
    def order(self, *a, **k): return self

    def range(self, desde, hasta):
        self.desde, self.hasta = desde, hasta
        return self

    def execute(self):
        hasta = self.hasta if self.hasta is not None else len(self.filas) - 1
        hasta = min(hasta, self.desde + self.TOPE - 1)
        return _Resp(self.filas[self.desde:hasta + 1])


class _Cli:
    def __init__(self, n):
        self.n = n

    def table(self, nombre):
        if nombre == "inspecciones":
            q = _Q([{"id": "x"}])
            q.single = lambda: type("S", (), {
                "execute": lambda self: _Resp({"id": "x"})})()
            return q
        return _Q([{"item": i, "abscisa": i} for i in range(self.n)])


@pytest.mark.parametrize("n", [0, 999, 1000, 1001, 16773])
def test_cargar_cips_trae_todas_las_filas(monkeypatch, n):
    # Supabase corta cada consulta en 1000 filas: un CIPS de 15 km
    # (~16.000 lecturas) se veía solo hasta el primer kilómetro.
    monkeypatch.setattr(db, "_client", lambda write=False: _Cli(n))
    det = db.cargar_inspeccion_cips("x")
    assert len(det["puntos"]) == n
    assert [p["item"] for p in det["puntos"]] == list(range(n))
    assert len(db.cargar_inspeccion_pap("x")["puntos"]) == n
    assert len(db.cargar_inspeccion_dcvg("x")["postes"]) == n
