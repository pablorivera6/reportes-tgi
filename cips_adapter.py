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


def _reparar_texto(s):
    """Repara mojibake del logger ('caÃ±o' -> 'caño'): el equipo exporta UTF-8
    leído como latin-1."""
    if 'Ã' in s or 'Â' in s:
        try:
            return s.encode('latin-1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            return s
    return s


# Errores de digitación frecuentes en los comentarios de campo. Solo palabras
# completas (con límites) y correcciones inequívocas.
_ORTOGRAFIA = {
    'cruse': 'cruce',
    'aerio': 'aéreo',
    'aereo': 'aéreo',
    'aerios': 'aéreos',
    'aereos': 'aéreos',
    'enseramiento': 'encerramiento',
    'enserramiento': 'encerramiento',
    'paryidura': 'partidura',
    'tencion': 'tensión',
    'tension': 'tensión',
    'valvula': 'válvula',
    'valvulas': 'válvulas',
    'linea': 'línea',
    'lineas': 'líneas',
    'rio': 'río',
    'abcisado': 'abscisado',
    'abcisa': 'abscisa',
    'medicion': 'medición',
    'proteccion': 'protección',
    'derivacion': 'derivación',
    'estacion': 'estación',
    'via': 'vía',
    'pk': 'PK',
}
_RE_PALABRA = re.compile(r'[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]+')
# 'en montado' -> 'enmontado' (tramo cubierto de monte) antes del corte por palabras
_RE_EN_MONTADO = re.compile(r'\ben\s+montado\b', re.IGNORECASE)


def _corregir_texto(s):
    """Corrige ortografía/digitación de un comentario de campo y lo deja con
    mayúscula inicial. No inventa contenido: solo sustituciones de palabra
    completa del diccionario _ORTOGRAFIA."""
    if not s:
        return s
    s = _RE_EN_MONTADO.sub('enmontado', s)

    def _sub(m):
        pal = m.group(0)
        rep = _ORTOGRAFIA.get(pal.lower())
        if rep is None:
            return pal
        if pal.isupper() and len(pal) > 2:
            return rep.upper()
        if pal[0].isupper():
            return rep[0].upper() + rep[1:]
        return rep

    s = _RE_PALABRA.sub(_sub, s)
    s = re.sub(r'\s{2,}', ' ', s).strip()
    if s and s[0].islower():
        s = s[0].upper() + s[1:]
    return s


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
    if ('aerio' in t or 'aereo' in t or 'aéreo' in t or 'salto' in t
            or 'montado' in t):
        return 'Tramo aéreo / salto'
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
        salida.append({
            "abscisa_val": abscisa_val,
            "referencia": comentario,
            "observaciones": comentario,
            "on_mv": _num(row.get("On_mV")),
            "off_mv": _num(row.get("Off_mV")),
            "on_limpio": _num(row.get("On_mV_limpio")),
            "off_limpio": _num(row.get("Off_mV_limpio")),
            "lat": _num(row.get("Lat_corr")),
            "lon": _num(row.get("Long_corr")),
        })
    return salida
