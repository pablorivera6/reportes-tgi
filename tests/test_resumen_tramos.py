"""Tabla de disponibilidad por tramo: qué tiene cada uno y si el PDF comparativo
vale la pena.

Sin esto, la "Vista por tramo" solo muestra una lista de nombres: hay que entrar
tramo por tramo para descubrir si tiene inspección actual, si tiene histórico
cargado, o las dos. Con 21 tramos y 51 históricos eso es inservible.
"""
import dashboard


INSP = [
    {"tipo": "DCVG", "tramo": "ramal salento", "fecha": "2026-07-14"},
    {"tipo": "CIPS", "tramo": "Salento", "fecha": "2026-07-15"},
    {"tipo": "DCVG", "tramo": "ramal praderas", "fecha": "2026-08-14"},
]
HIST = [
    {"tipo": "DCVG", "tramo": "Salento", "periodo": "Abr 2024"},
    {"tipo": "CIPS", "tramo": "Salento", "periodo": "Nov 2023"},
    {"tipo": "DCVG", "tramo": "Alvarado", "periodo": "Jun 2024"},
]


def _mismo(a, b):
    """Emparejador de prueba: 'ramal salento' == 'Salento'."""
    limpia = lambda t: (t or "").lower().replace("ramal ", "").strip()
    return limpia(a) == limpia(b)


def _por(filas, tramo):
    return next(f for f in filas if f["tramo"] == tramo)


def test_lista_un_tramo_por_nombre_sin_duplicar():
    filas = dashboard.resumen_por_tramo(INSP, HIST, mismo=_mismo)
    tramos = [f["tramo"] for f in filas]
    assert len(tramos) == len(set(tramos))
    # Salento aparece como 'ramal salento' y 'Salento': es UN tramo
    assert sum(1 for t in tramos if "salento" in t.lower()) == 1


def test_cuenta_tecnicas_actuales_y_historicos():
    f = _por(dashboard.resumen_por_tramo(INSP, HIST, mismo=_mismo), "ramal salento")
    assert sorted(f["tipos"]) == ["CIPS", "DCVG"]
    assert f["n_actuales"] == 2
    assert f["n_historicos"] == 2


def test_marca_comparativa_solo_si_hay_ACTUAL_e_HISTORICO_del_mismo_tipo():
    """Un histórico CIPS no se compara con una inspección DCVG: son técnicas
    distintas. Fue el caso de Palestina."""
    filas = dashboard.resumen_por_tramo(
        [{"tipo": "DCVG", "tramo": "Palestina", "fecha": "2026-07-23"}],
        [{"tipo": "CIPS", "tramo": "Palestina", "periodo": "Nov 2024"}],
        mismo=_mismo)
    f = _por(filas, "Palestina")
    assert f["n_historicos"] == 1
    assert f["comparativa"] is False


def test_comparativa_true_cuando_coincide_la_tecnica():
    f = _por(dashboard.resumen_por_tramo(INSP, HIST, mismo=_mismo), "ramal salento")
    assert f["comparativa"] is True


def test_tramo_sin_historico():
    f = _por(dashboard.resumen_por_tramo(INSP, HIST, mismo=_mismo), "ramal praderas")
    assert f["n_historicos"] == 0
    assert f["comparativa"] is False


def test_historico_sin_inspeccion_no_entra():
    """La vista se arma desde inspecciones publicadas (decisión del usuario:
    un tramo que solo tiene histórico no aparece todavía)."""
    tramos = [f["tramo"] for f in dashboard.resumen_por_tramo(INSP, HIST, mismo=_mismo)]
    assert "Alvarado" not in tramos


def test_ordena_primero_los_que_tienen_comparativa():
    """Lo accionable arriba: el PDF comparativo es lo que se va a descargar."""
    filas = dashboard.resumen_por_tramo(INSP, HIST, mismo=_mismo)
    assert filas[0]["comparativa"] is True


def test_sin_datos_devuelve_lista_vacia():
    assert dashboard.resumen_por_tramo([], [], mismo=_mismo) == []
