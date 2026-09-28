"""PDF de un histórico que todavía no tiene inspección actual.

Cuando se carga el histórico de un tramo que aún no se ha vuelto a inspeccionar
no hay tablero que exportar (el PDF del dashboard se arma sobre la inspección).
`pdf_historico` produce igual el documento de la campaña anterior, dejando
explícito que no hay comparación posible todavía.
"""
import pytest

import comparativa

HIST = {
    "tramo": "Neira", "tipo": "DCVG", "periodo": "May 2024",
    "fuente": "TELMACOM SAS · DCVG_REP_R_NEIR_06_24.xlsx",
    "resumen": {"n_defectos": 3, "n_postes": 2, "n_criticos": 1,
                "por_clasificacion": {"Muy Pequeño": 2, "Pequeño": 0,
                                      "Mediano": 1, "Grande": 0},
                "long_m": 22050, "densidad_km": 0.14,
                "prom_severidad": 12.0, "max_severidad": 40.0},
    "puntos": [
        {"clase": "poste", "abscisa": 0, "referencia": "Poste de Potencial",
         "on": -1400, "off": -1050},
        {"clase": "poste", "abscisa": 22050, "referencia": "Citygate",
         "on": -1300, "off": -980},
        {"clase": "defecto", "abscisa": 510, "caracter": "CA", "ol_re": 22,
         "p_re": 197.5, "severidad_pct": 11.1, "clasificacion": "Muy Pequeño",
         "profundidad": 2.6},
        {"clase": "defecto", "abscisa": 8300, "caracter": "CC", "ol_re": 9,
         "p_re": 385.4, "severidad_pct": 2.3, "clasificacion": "Muy Pequeño",
         "profundidad": 1.5},
        {"clase": "defecto", "abscisa": 15000, "caracter": "AA", "ol_re": 260,
         "p_re": 614.2, "severidad_pct": 40.0, "clasificacion": "Mediano",
         "profundidad": 2.0},
    ],
}


def _texto(pdf_bytes):
    pypdf = pytest.importorskip("pypdf")
    import io
    r = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return len(r.pages), "\n".join(p.extract_text() or "" for p in r.pages)


def test_genera_un_pdf_valido():
    b = comparativa.pdf_historico(HIST)
    assert b[:4] == b"%PDF"
    paginas, _ = _texto(b)
    assert paginas >= 1


def test_lleva_el_tramo_el_periodo_y_la_fuente():
    _, txt = _texto(comparativa.pdf_historico(HIST))
    assert "Neira" in txt
    assert "May 2024" in txt
    assert "TELMACOM" in txt


def test_dice_que_no_hay_inspeccion_actual_con_que_comparar():
    """Lo importante: que nadie lea este PDF como si fuera una comparativa."""
    _, txt = _texto(comparativa.pdf_historico(HIST))
    assert "sin inspección actual" in txt.lower()


def test_incluye_los_defectos_y_su_severidad():
    _, txt = _texto(comparativa.pdf_historico(HIST))
    assert "Mediano" in txt
    assert "K 015+000" in txt          # la abscisa del defecto mediano
    assert "40" in txt                 # su severidad %IR


def test_funciona_sin_defectos():
    """Varios históricos DCVG no encontraron ni un defecto: no debe reventar."""
    h = dict(HIST)
    h["puntos"] = [p for p in HIST["puntos"] if p["clase"] == "poste"]
    h["resumen"] = dict(HIST["resumen"], n_defectos=0, n_criticos=0,
                        por_clasificacion={"Muy Pequeño": 0, "Pequeño": 0,
                                           "Mediano": 0, "Grande": 0},
                        max_severidad=None, prom_severidad=None)
    b = comparativa.pdf_historico(h)
    assert b[:4] == b"%PDF"
    _, txt = _texto(b)
    assert "Neira" in txt
