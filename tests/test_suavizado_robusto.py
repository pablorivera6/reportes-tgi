"""El suavizado de picos debe: (1) limpiar picos aislados, (2) limpiar picos
en los EXTREMOS (antes quedaban sin tocar por center=True sin min_periods),
(3) limpiar RACIMOS cortos de lecturas malas, PERO (4) preservar una zona de
baja protección real (caída sostenida) — que es justo lo que el survey busca."""
import numpy as np
import pandas as pd

from cips_lrs import _suavizar_outliers


def _base(n=400, nivel=-1200.0):
    return pd.Series([nivel] * n, dtype=float)


def test_pico_aislado_medio():
    s = _base()
    s.iloc[200] = -3000.0
    out = _suavizar_outliers(s)
    assert abs(out.iloc[200] - (-1200)) < 50


def test_pico_en_extremos():
    s = _base()
    s.iloc[0] = -3000.0
    s.iloc[-1] = -500.0
    out = _suavizar_outliers(s)
    assert abs(out.iloc[0] - (-1200)) < 50, "no suaviza el primer punto"
    assert abs(out.iloc[-1] - (-1200)) < 50, "no suaviza el último punto"


def test_racimo_corto():
    s = _base()
    s.iloc[100:106] = -3000.0     # 6 lecturas malas seguidas
    out = _suavizar_outliers(s)
    assert (abs(out.iloc[100:106] - (-1200)) < 50).all()


def test_preserva_baja_proteccion_real():
    # zona de 40 puntos genuinamente desprotegida (~-650 mV): NO se debe borrar
    s = _base()
    s.iloc[200:240] = -650.0
    out = _suavizar_outliers(s)
    assert (abs(out.iloc[205:235] - (-650)) < 30).all(), "borró baja protección real"
