"""Lógica pura del dashboard de visualización (independiente de Streamlit,
para poder testearla). Convierte la data procesada en KPIs y puntos listos
para mapa/gráfica.

Criterios de protección catódica (NACE SP0169), sobre el potencial Instant-OFF:
  OFF <= -1200 mV  -> Sobreprotegido
  -1200 < OFF <= -850 -> Protegido
  OFF > -850 mV    -> Desprotegido
"""

CRITERIO_OK = -850
CRITERIO_SOBRE = -1200

# Colores por estado (para el mapa): verde protegido, rojo desprotegido,
# azul sobreprotegido, gris sin dato.
COLOR_ESTADO = {
    "Protegido": "#1A7A4A",
    "Desprotegido": "#C7113A",
    "Sobreprotegido": "#1F6FEB",
    "Sin dato": "#9CA3AF",
}


def estado_cp(off):
    """Estado de protección de un punto según su potencial Instant-OFF (mV)."""
    if off is None:
        return "Sin dato"
    try:
        off = float(off)
    except (TypeError, ValueError):
        return "Sin dato"
    if off <= CRITERIO_SOBRE:
        return "Sobreprotegido"
    if off <= CRITERIO_OK:
        return "Protegido"
    return "Desprotegido"


def _off(punto):
    v = punto.get("off_limpio")
    if v is None:
        v = punto.get("off_mv")
    return v


def resumen_cips(cips):
    """Devuelve KPIs + lista de puntos con estado/color para el dashboard CIPS.

    KPIs: total, protegido, desprotegido, sobreprotegido, con_dato,
    pct_protegido (sobre los puntos con dato).
    """
    puntos = []
    conteo = {"Protegido": 0, "Desprotegido": 0, "Sobreprotegido": 0, "Sin dato": 0}
    for c in cips or []:
        off = _off(c)
        est = estado_cp(off)
        conteo[est] += 1
        puntos.append({
            "abscisa_val": c.get("abscisa_val"),
            "lat": c.get("lat"),
            "lon": c.get("lon"),
            "on": c.get("on_limpio") if c.get("on_limpio") is not None else c.get("on_mv"),
            "off": off,
            "estado": est,
            "color": COLOR_ESTADO[est],
            "observaciones": c.get("observaciones", ""),
        })
    con_dato = sum(v for k, v in conteo.items() if k != "Sin dato")
    pct = round(100 * conteo["Protegido"] / con_dato, 1) if con_dato else 0.0
    return {
        "total": len(puntos),
        "con_dato": con_dato,
        "protegido": conteo["Protegido"],
        "desprotegido": conteo["Desprotegido"],
        "sobreprotegido": conteo["Sobreprotegido"],
        "pct_protegido": pct,
        "puntos": puntos,
    }
