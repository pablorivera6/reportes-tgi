"""Transforma el JSON de un submission de FastField al modelo de datos del sistema.

Por ahora: PAP (formulario 'Inspeccion PAP-PBI', subform_1 = postes).
DCVG/Resistividades se agregan igual cuando tengamos un submission de ejemplo.
"""
from __future__ import annotations

import re


def _v(x):
    """Desenvuelve los listpicker que vienen como lista de 1 valor."""
    if isinstance(x, list):
        return x[0] if x else None
    return x


def _num(x):
    try:
        if x is None or x == "":
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_pk(txt):
    """'220+000' / 'K 220+000' -> metros (int)."""
    if txt is None:
        return None
    m = re.search(r'(\d{1,4})\s*\+\s*(\d{1,3})', str(txt))
    if not m:
        return None
    return int(m.group(1)) * 1000 + int(m.group(2))


def _fotos_de_item(item):
    fns = []
    for k, val in item.items():
        if k.startswith("multiphoto_picker") and isinstance(val, list):
            for ph in val:
                if isinstance(ph, dict) and ph.get("photo"):
                    fns.append(ph["photo"])
    return fns


def pap_submission(sub: dict):
    """FastField 'Inspeccion PAP-PBI' -> (info, potenciales, fotos_por_poste).

    fotos_por_poste: dict {abscisa_str: [filenames]} para el registro fotográfico.
    """
    postes = sub.get("subform_1") or []
    potenciales, fotos = [], {}
    tramo = gasoducto = None
    for i, p in enumerate(postes):
        u = p.get("Ubicacion") or {}
        absc = p.get("Abscisa")
        tramo = _v(p.get("listpicker_7")) or tramo
        gasoducto = _v(p.get("listpicker_8")) or gasoducto
        potenciales.append({
            "abscisa_str": absc, "abscisa": parse_pk(absc), "pk_m": parse_pk(absc),
            "on_mv": _num(p.get("POn")), "off_mv": _num(p.get("POff")),
            "potencial_natural": _num(p.get("PNatural")),
            "polarizacion": _num(p.get("Polarizacion")),
            "vac": _num(p.get("voltaje_ac")),
            "resistencia": _num(p.get("resistencia_neg1_neg2")),
            "ir_on_off": _num(p.get("IROn")),
            "lat": _num(u.get("latitude")), "lon": _num(u.get("longitude")),
            "ref_geografica": _v(p.get("referencia_geografica_pap")),
            "observaciones": p.get("Comentario") or "",
            "pintura": _v(p.get("estado_pintura")),
            "conexiones": _v(p.get("estado_conexiones")),
            "verticalidad": _v(p.get("estado_verticalidad")),
            "tramo": tramo,
        })
        fns = _fotos_de_item(p)
        if fns:
            fotos[str(absc or i)] = fns

    fecha = (sub.get("datepicker_1") or sub.get("submissionTimeStamp") or "")[:10]
    info = {
        "tramo": tramo, "gasoducto": gasoducto, "tipo_inspeccion": "PAP",
        "inspector": _v(sub.get("listpicker_1")), "fecha": fecha,
        "submissionId": sub.get("submissionId"), "formName": sub.get("formName"),
    }
    return info, potenciales, fotos


def aislamientos_submission(sub: dict):
    """FastField 'Aislamientos..' -> (info, aislamientos, fotos_por_junta)."""
    juntas = sub.get("subform_1") or []
    aisl, fotos = [], {}
    for i, j in enumerate(juntas):
        u = j.get("ubicaciongps_aislamientos") or {}
        aisl.append({
            "abscisado": (j.get("Abscisado_Aislamientos") or "").strip() or None,
            "tag": _v(j.get("Tag_aislamiento")),
            "diametro": _num(j.get("numeric_1")),
            "tipo_brida": _v(j.get("Tipo_brida")),
            "tipo_aislamiento": _v(j.get("Tipo_aislamiento")),
            "numero_pernos": _num(j.get("Numero_pernos")),
            "diametro_pernos": _num(j.get("Diametro_pernos")),
            "presion_psi": _num(j.get("Presion_psi")),
            "aislamiento_caras": _num(j.get("Aislamientoelectricoentrecaras")),
            "pot_on_arriba": _num(j.get("on_aguasarriba")),
            "pot_off_arriba": _num(j.get("off_aguasarriba")),
            "pot_on_abajo": _num(j.get("on_aguasabajo")),
            "pot_off_abajo": _num(j.get("off_aguasabajo")),
            "pot_on_diferencia": _num(j.get("on_diferencia")),
            "pot_off_diferencia": _num(j.get("off_diferencia")),
            "diagnostico": _v(j.get("Diagnostico_aslamientos")),
            "observaciones": j.get("Observaciones_aislamientos") or "",
            "lat": _num(u.get("latitude")), "lon": _num(u.get("longitude")),
        })
        fns = _fotos_de_item(j)
        if fns:
            fotos[str(j.get("Abscisado_Aislamientos") or i)] = fns
    fecha = (sub.get("datepicker_1") or sub.get("submissionTimeStamp") or "")[:10]
    info = {
        "tramo": (sub.get("alpha_1") or "").strip() or None,
        "gasoducto": _v(sub.get("listpicker_1")),
        "tipo_inspeccion": "AISLAMIENTOS", "fecha": fecha,
        "inspector": _v(sub.get("listpicker_1")),
        "submissionId": sub.get("submissionId"), "formName": sub.get("formName"),
    }
    return info, aisl, fotos


# Mapa formId -> (tipo, funcion_transform).  Completar con los ids reales.
FORM_MAP = {
    "1199286": ("PAP", pap_submission),               # Inspeccion PAP-PBI
    "1240049": ("AISLAMIENTOS", aislamientos_submission),  # Aislamientos..
    # "1160295": ("RESIST", ...),   # "Inspección DCVG" = en realidad resistividades
    # DCVG de defectos: confirmar cuál form (¿DCVG PBI 1206115?)
}
