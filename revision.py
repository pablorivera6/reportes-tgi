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

# ── Categorías de rechazo ───────────────────────────────────────────────────
# Cada una termina en un sitio distinto: por eso el rechazo se clasifica en vez
# de ser un párrafo suelto.
CATEGORIAS = ("datos_generales", "procesamiento", "texto_campo", "falta_info")

_ETIQUETAS = {
    "datos_generales": "Datos Generales (tramo, OT, contrato, fechas)",
    "procesamiento": "Procesamiento (abscisa, tramo, picos, clasificación)",
    "texto_campo": "Texto de campo (comentarios, hallazgos, conclusiones)",
    "falta_info": "Falta información (la debe subir el técnico)",
}


def etiqueta(categoria):
    """Nombre legible de una categoría, para la UI."""
    return _ETIQUETAS.get(categoria, categoria)


def _entero(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def normalizar(obs):
    """Completa y valida una observación venga de donde venga (formulario del
    revisor, `st.data_editor` o la IA). Lanza ValueError si la categoría no es
    una de las cuatro: es la única forma de enrutar bien la devolución."""
    cat = str(obs.get("categoria") or "").strip()
    if cat not in CATEGORIAS:
        raise ValueError(
            f"Categoría '{cat}' inválida. Debe ser una de: {', '.join(CATEGORIAS)}")
    return {
        "categoria": cat,
        "campo": (str(obs["campo"]).strip() or None) if obs.get("campo") else None,
        "abscisa_ini": _entero(obs.get("abscisa_ini")),
        "abscisa_fin": _entero(obs.get("abscisa_fin")),
        "nota": (str(obs.get("nota") or "").strip() or None),
        "origen": obs.get("origen") or "revisor",
        "estado": obs.get("estado") or "abierta",
    }


def requiere_crudos(observaciones):
    """¿Alguna observación obliga a reprocesar desde los archivos del técnico?
    Solo 'procesamiento': lo demás se arregla con la data ya publicada."""
    return any(o.get("categoria") == "procesamiento" for o in observaciones or [])


def es_para_tecnico(obs):
    """'falta_info' no abre el buzón: no hay nada que corregir en el generador,
    falta un archivo que solo el técnico puede subir."""
    return obs.get("categoria") == "falta_info"


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

_PAP = {
    "abscisa": "abscisa", "fecha": "fecha", "on_mv": "on_mv", "off_mv": "off_mv",
    "natural_mv": "potencial_natural", "polarizacion_mv": "polarizacion",
    "vac_mv": "vac", "ir_on_off": "ir_on_off", "resistencia": "resistencia",
    "lat": "lat", "lon": "lon", "ref_geografica": "ref_geografica",
    "observaciones": "observaciones",
}

_POSTES = {
    "abscisa": "pk_m", "tipo": "tipo", "on_mv": "on", "off_mv": "off",
    "vac_mv": "vac", "resistencia": "resistencia", "lat": "lat", "lon": "lon",
}

# p_re / severidad_pct / clasificacion NO están: los recalcula _severidad_dcvg.
_DEFECTOS = {
    "abscisa": "pk_m", "sector": "sector",
    "forma_n": "forma_n", "forma_e": "forma_e",
    "forma_s": "forma_s", "forma_o": "forma_o",
    "caracter": "caracter", "ol_re": "ol_re", "profundidad": "profundidad",
    "posicion_reloj": "posicion_reloj", "lat": "lat", "lon": "lon",
    "comentarios": "comentarios",
}

_RESIST = {
    "abscisa": "pk_m", "sector": "sector", "profundidad": "profundidad",
    "r1": "r1", "r2": "r2", "r3": "r3", "lat": "lat", "lon": "lon",
}

_HALLAZGOS = {
    "abscisa_ini": "abscisa_val", "abscisa_fin": "abscisa_fin",
    "longitud_m": "longitud", "lat_ini": "lat", "lon_ini": "lon",
    "lat_fin": "lat_fin", "lon_fin": "lon_fin",
    "fecha": "fecha", "tipo": "tipo", "descripcion": "descripcion",
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


def pap_desde_filas(filas):
    """`puntos_pap` → dicts de `data['potenciales']`."""
    return _mapear(filas, _PAP)


def postes_desde_filas(filas):
    """`postes_dcvg` → dicts de `data['dcvg_postes']`."""
    return _mapear(filas, _POSTES)


def defectos_desde_filas(filas):
    """`defectos_dcvg` → dicts de `data['dcvg_defectos']` (sin derivados)."""
    return _mapear(filas, _DEFECTOS)


def resist_desde_filas(filas):
    """`resistividades_dcvg` → dicts de `data['dcvg_resist']`."""
    return _mapear(filas, _RESIST)


def hallazgos_desde_filas(filas):
    """`hallazgos` → dicts de `data['hallazgos']` / `data['dcvg_hallazgos']`."""
    return _mapear(filas, _HALLAZGOS)


# Campos de `info` que la fila `inspecciones` sí guarda, por si no hay contexto
# (informes publicados antes del esquema v9).
_INFO_DE_FILA = ("gasoducto", "tramo", "fecha", "inspector", "ciclo", "ot",
                 "contratista", "serial_equipo", "tipo_recubrimiento", "diametro")


def rehidratar(detalle, tipo):
    """Detalle de `db.cargar_inspeccion_*` → dicts listos para `data`.

    `info` sale del `contexto` snapshoteado al publicar (es el completo) y se
    completa con las columnas de la fila cuando falte algo. Devuelve solo las
    claves del tipo, para no pisar listas de otros tipos en la sesión.
    """
    insp = (detalle or {}).get("inspeccion") or {}
    info = dict((insp.get("contexto") or {}).get("info") or {})
    for col in _INFO_DE_FILA:
        if not info.get(col) and insp.get(col):
            info[col] = insp[col]
    info["tipo_inspeccion"] = insp.get("tipo") or tipo

    out = {"info": info}
    if tipo == "CIPS":
        out["cips"] = cips_desde_filas(detalle.get("puntos"))
        out["hallazgos"] = hallazgos_desde_filas(detalle.get("hallazgos"))
    elif tipo == "PAP":
        out["potenciales"] = pap_desde_filas(detalle.get("puntos"))
        out["hallazgos"] = hallazgos_desde_filas(detalle.get("hallazgos"))
    else:
        out["dcvg_postes"] = postes_desde_filas(detalle.get("postes"))
        out["dcvg_defectos"] = defectos_desde_filas(detalle.get("defectos"))
        out["dcvg_resist"] = resist_desde_filas(detalle.get("resistividades"))
        out["dcvg_hallazgos"] = hallazgos_desde_filas(detalle.get("hallazgos"))
    return out
