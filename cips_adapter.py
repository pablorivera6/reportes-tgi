"""Adaptador: DataFrame del motor CIPS-LRS -> list[dict] para generator.fill_cips.

Las columnas Far/Near/Metal Ground y VAC no las produce el motor LRS; se dejan
ausentes para que fill_cips escriba celdas vacías (comportamiento de proceso-cips).
"""
import math
import re

import pandas as pd

# Comentario que es SOLO un marcador de abscisado ('pk 1+000', '0+031',
# 'PK 002+000 No existe', 'pk 5+000 abcisado'): no es un hallazgo.
_RE_MARCADOR = re.compile(
    r'^\s*(?:pk|km)?\s*\d{1,3}\s*\+\s*\d{1,3}\s*'
    r'(?:abcisado|abscisado|poste\s+abscisado|no\s+existe|sin\s+cables)?\s*$',
    re.IGNORECASE)


# Corrección centralizada (aplica a todos los informes); alias con guión bajo
# por compatibilidad con los tests y usos internos.
from ortografia import corregir_texto as _corregir_texto
from ortografia import reparar_texto as _reparar_texto


def _tipo_hallazgo(texto):
    t = texto.lower()
    if 'cable' in t or 'partid' in t:
        return 'Cable de medición partido'
    if 'cruce' in t or 'cruse' in t:
        return 'Cruce'
    if 'valvula' in t or 'válvula' in t:
        return 'Válvula'
    if 'malla' in t or 'enseramiento' in t or 'encerramiento' in t:
        return 'Malla / encerramiento'
    # Tramo enmontado/sin rocería: la cuadrilla no pudo pasar (pasto alto o
    # terreno intransitable) y ese tramo quedó sin inspeccionar ("salto").
    if ('montado' in t or 'rocería' in t or 'roceria' in t or 'salto' in t
            or 'sin paso' in t or 'sipaso' in t):
        return 'Tramo sin rocería / no inspeccionado'
    if 'aerio' in t or 'aereo' in t or 'aéreo' in t:
        return 'Tramo aéreo'
    if 'interfase' in t or 'interface' in t:
        return 'Interfase tierra-aire'
    return 'Observación de campo'


def cips_a_hallazgos(cips_dicts):
    """Convierte los comentarios de campo del survey CIPS en hallazgos para
    generator.fill_hallazgos (abscisa, coordenadas, tipo y descripción).
    Gasoducto/tramo/fecha los completa fill_hallazgos desde info."""
    hallazgos = []
    for d in cips_dicts:
        obs = str(d.get('observaciones') or d.get('referencia') or '').strip()
        if not obs or obs.lower() == 'nan' or _RE_MARCADOR.match(obs):
            continue
        hallazgos.append({
            'abscisa_val': d.get('abscisa_val'),
            'abscisa_fin': '',
            'longitud': '',
            'lat': d.get('lat'),
            'lon': d.get('lon'),
            'fecha': d.get('fecha'),
            'tipo': _tipo_hallazgo(obs),
            'descripcion': obs,
        })
    return hallazgos


def _num(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return v


def lrs_df_a_cips_dicts(df):
    salida = []
    for _, row in df.iterrows():
        # Abscisa = PK geométrico del motor LRS (GPS sobre la traza), igual
        # que la app original proceso-cips.
        pk = row.get("PK_geom_m")
        abscisa_val = int(round(pk)) if pd.notna(pk) else 0
        comentario = str(row.get("Comentarios", "") or "").strip()
        if comentario.lower() in ("nan", "none"):
            comentario = ""
        comentario = _corregir_texto(_reparar_texto(comentario))
        fecha = row.get("Fecha_dato")
        fecha = str(fecha) if (fecha is not None and pd.notna(fecha)) else None
        salida.append({
            "abscisa_val": abscisa_val,
            "referencia": comentario,
            "observaciones": comentario,
            "fecha": fecha,
            "on_mv": _num(row.get("On_mV")),
            "off_mv": _num(row.get("Off_mV")),
            "on_limpio": _num(row.get("On_mV_limpio")),
            "off_limpio": _num(row.get("Off_mV_limpio")),
            "metal_on": _num(row.get("metal_on_mv")),
            "metal_off": _num(row.get("metal_off_mv")),
            "far_on": _num(row.get("far_on_mv")),
            "far_off": _num(row.get("far_off_mv")),
            "near_on": _num(row.get("near_on_mv")),
            "near_off": _num(row.get("near_off_mv")),
            "lat": _num(row.get("Lat_corr")),
            "lon": _num(row.get("Long_corr")),
        })
    return _quitar_duplicados(salida)


_CLAVES_COMPLETAR = ("metal_on", "metal_off", "far_on", "far_off",
                     "near_on", "near_off", "vac")


def _quitar_duplicados(salida):
    """Elimina ÚNICAMENTE lecturas repetidas exactas — misma abscisa Y mismos
    potenciales/coordenadas — que aparecen cuando dos exportes del logger se
    solapan. Las lecturas DISTINTAS que caen en el mismo metro se CONSERVAN
    (una inspección CIPS densa tiene varias lecturas por metro; colapsarlas
    perdía calidad de data). Al eliminar un repetido, su comentario y sus
    lecturas DCP (Metal/Far/Near) se traspasan a la que queda."""
    vistos = {}
    orden = []
    for d in salida:
        clave = (d.get("abscisa_val"), d.get("on_mv"), d.get("off_mv"),
                 d.get("on_limpio"), d.get("off_limpio"),
                 d.get("lat"), d.get("lon"))
        if clave not in vistos:
            vistos[clave] = d
            orden.append(clave)
            continue
        base = vistos[clave]              # repetido exacto: fusionar y descartar
        for k in _CLAVES_COMPLETAR:
            if base.get(k) is None and d.get(k) is not None:
                base[k] = d[k]
        for k in ("observaciones", "referencia"):
            txt = d.get(k)
            if txt and txt not in (base.get(k) or ""):
                base[k] = f"{base[k]} | {txt}" if base.get(k) else txt
    return [vistos[c] for c in orden]
