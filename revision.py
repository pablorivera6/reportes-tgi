"""Devolución de informes rechazados: modelo de observaciones y rehidratación.

La inversa de los constructores `db._*_filas`. Las columnas de la BD y las
claves que espera el generador NO se llaman igual (`abscisa` vs `abscisa_val`,
`lejano_on` vs `far_on`), así que el mapeo es explícito y está cubierto por
tests de ida y vuelta: si se desincroniza, el informe corregido sale con datos
corridos sin lanzar ningún error.

Los campos DERIVADOS (`estado`, `p_re`, `severidad_pct`, `clasificacion`) no se
rehidratan: `dashboard.estado_cp` y `db._severidad_dcvg` los recalculan al
publicar. Eso elimina el riesgo de que un % vuelva como fracción.

Sin Streamlit y sin red: todo aquí es puro.
"""
from __future__ import annotations

# ── Mapeos columna BD → clave del generador ─────────────────────────────────
_CIPS = {
    "abscisa": "abscisa_val", "fecha": "fecha",
    "on_mv": "on_mv", "off_mv": "off_mv",
    "on_limpio": "on_limpio", "off_limpio": "off_limpio",
    "natural_mv": "natural_mv", "polarizacion_mv": "polarizacion_mv",
    "vac_mv": "vac_mv", "metal_on": "metal_on", "metal_off": "metal_off",
    "lejano_on": "far_on", "lejano_off": "far_off",
    "cercano_on": "near_on", "cercano_off": "near_off",
    "ir_on_off": "ir_on_off", "lat": "lat", "lon": "lon",
    "observaciones": "observaciones",
}


def _mapear(filas, mapa):
    """Traduce filas de la BD a dicts del generador, omitiendo los None que la
    BD rellenó y toda columna que no esté en el mapa (ids, derivados)."""
    salida = []
    for f in filas or []:
        d = {}
        for col, clave in mapa.items():
            v = f.get(col)
            if v is not None:
                d[clave] = v
        salida.append(d)
    return salida


def cips_desde_filas(filas):
    """`puntos_cips` → dicts de `data['cips']`."""
    return _mapear(filas, _CIPS)
