"""Corrección de ortografía/digitación de los textos de campo.

Se aplica a TODO texto libre que entra a los informes (PAP, CIPS, hallazgos,
aislamientos, inspecciones y PPM). Solo hace sustituciones de palabra completa
de un diccionario cerrado + tildes + mayúscula inicial: nunca inventa ni
parafrasea lo que escribió el técnico.
"""
import re

# Errores de digitación frecuentes en los comentarios de campo.
ORTOGRAFIA = {
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
    'sipaso': 'sin paso',
    'roceria': 'rocería',
    'medicion': 'medición',
    'proteccion': 'protección',
    'derivacion': 'derivación',
    'estacion': 'estación',
    'via': 'vía',
    'pk': 'PK',
}
_RE_PALABRA = re.compile(r'[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]+')
# 'en montado' -> 'enmontado' (tramo cubierto de monte)
_RE_EN_MONTADO = re.compile(r'\ben\s+montado\b', re.IGNORECASE)


def reparar_texto(s):
    """Repara mojibake del logger ('caÃ±o' -> 'caño'): el equipo exporta UTF-8
    leído como latin-1."""
    if 'Ã' in s or 'Â' in s:
        try:
            return s.encode('latin-1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            return s
    return s


def corregir_texto(s):
    """Corrige ortografía/digitación de un texto de campo y lo deja con
    mayúscula inicial. Idempotente."""
    if not s:
        return s
    s = _RE_EN_MONTADO.sub('enmontado', s)

    def _sub(m):
        pal = m.group(0)
        rep = ORTOGRAFIA.get(pal.lower())
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


def corregir_campo(v):
    """Versión segura para celdas: corrige solo si es un str con contenido;
    números, fechas y None pasan intactos."""
    if isinstance(v, str) and v.strip():
        return corregir_texto(reparar_texto(v))
    return v
