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
    """Todas las fotos de un item: multiphoto_picker_* (listas) + photo_picker_* (string)."""
    fns = []
    for k, val in item.items():
        if k.startswith("multiphoto_picker") and isinstance(val, list):
            for ph in val:
                if isinstance(ph, dict) and ph.get("photo"):
                    fns.append(ph["photo"])
        elif k.startswith("photo_picker") and isinstance(val, str) and val.strip():
            fns.append(val.strip())
    return fns


def _loc(item, *keys):
    """(lat, lon) del primer LocationPicker que exista (por defecto 'location_1')."""
    for k in (keys or ("location_1",)):
        u = item.get(k)
        if isinstance(u, dict):
            return _num(u.get("latitude")), _num(u.get("longitude"))
    return None, None


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


def _clasif_ir(pct):
    """Clasificación NACE por %IR (SP0502): <15 leve, 15-35 moderado, 35-60 severo, >60 crítico."""
    if pct is None:
        return None
    if pct < 15:
        return "Leve"
    if pct < 35:
        return "Moderado"
    if pct < 60:
        return "Severo"
    return "Crítico"


def dcvg_submission(sub: dict):
    """FastField 'Inspección DCVG' (form 1160295) -> todas las secciones.

    Un solo formulario con 5 subforms repetibles:
      subform_5 = Poste (PAP)   subform_6 = Hallazgos   subform_7 = Resistividades
      subform_8 = Hallazgo simple   subform_9 = Defecto (DCVG)

    Devuelve dict con info + una lista por sección (cada elemento con sus fotos en 'fotos').
    """
    def _rows(key):
        return sub.get(key) or []

    # ── Postes (PAP) ──────────────────────────────────────────────────────
    postes = []
    for p in _rows("subform_5"):
        lat, lon = _loc(p)
        postes.append({
            "tipo_poste": _v(p.get("listpicker_5")),
            "abscisa_str": p.get("alpha_2"), "pk_m": parse_pk(p.get("alpha_2")),
            "on_mv": _num(p.get("numeric_1")), "off_mv": _num(p.get("numeric_2")),
            "vac": _num(p.get("numeric_3")), "resistencia": _num(p.get("numeric_4")),
            "pintura": _v(p.get("listpicker_1")),
            "conexiones": _v(p.get("listpicker_2")),
            "verticalidad": _v(p.get("listpicker_3")),
            "tipo_mantenimiento": _v(p.get("listpicker_4")),
            "lat": lat, "lon": lon,
            "fotos": _fotos_de_item(p),
        })

    # ── Hallazgos ─────────────────────────────────────────────────────────
    hallazgos = []
    for h in _rows("subform_6"):
        ini, fin = _num(h.get("numeric_1")), _num(h.get("numeric_2"))
        hallazgos.append({
            "tipo": _v(h.get("listpicker_1")),
            "abscisa_inicio": ini, "abscisa_fin": fin,
            "longitud": (fin - ini) if (ini is not None and fin is not None) else _num(h.get("computedlabel_1")),
            "fotos": _fotos_de_item(h),
        })

    # ── Hallazgos simples ─────────────────────────────────────────────────
    hallazgos_simples = []
    for h in _rows("subform_8"):
        lat, lon = _loc(h)
        hallazgos_simples.append({
            "tipo": _v(h.get("listpicker_1")),
            "abscisa_str": h.get("alpha_1"), "pk_m": parse_pk(h.get("alpha_1")),
            "lat": lat, "lon": lon,
            "fotos": _fotos_de_item(h),
        })

    # ── Resistividades ────────────────────────────────────────────────────
    resistividades = []
    for r in _rows("subform_7"):
        lat, lon = _loc(r)
        resistividades.append({
            "abscisa_str": r.get("alpha_1"), "pk_m": parse_pk(r.get("alpha_1")),
            "sector": r.get("alpha_2"),
            "profundidad": _num(r.get("numeric_1")),
            "r_1m": _num(r.get("numeric_2")),
            "r_2m": _num(r.get("numeric_3")),
            "r_3m": _num(r.get("numeric_4")),
            "lat": lat, "lon": lon,
            "fotos": _fotos_de_item(r),
        })

    # ── Defectos (DCVG) ───────────────────────────────────────────────────
    defectos = []
    for d in _rows("subform_9"):
        lat, lon = _loc(d)
        ol_re = _num(d.get("numeric_4"))          # OL/RE
        p_re = _num(d.get("numeric_5"))           # Severidad (P/RE)
        ir = _num(d.get("computedlabel_1"))       # %IR ya calculado (fracción)
        if ir is None and ol_re is not None and p_re:
            ir = ol_re / p_re
        ir_pct = round(ir * 100, 2) if ir is not None else None
        defectos.append({
            "abscisa_str": d.get("alpha_2"), "pk_m": parse_pk(d.get("alpha_2")),
            "sector": d.get("alpha_9"),
            "status_on": d.get("alpha_1"), "status_off": d.get("alpha_7"),
            "ol_re": ol_re, "p_re": p_re,
            "ir_pct": ir_pct,
            "clasificacion": _v(d.get("listpicker_3")),        # clasificación del técnico
            "clasificacion_ir": _clasif_ir(ir_pct),            # calculada por %IR (NACE)
            "profundidad_m": _num(d.get("numeric_3")),
            "forma_defecto": _v(d.get("listpicker_2")),
            "caracter": _v(d.get("listpicker_4")),
            "forma_n": d.get("alpha_3"), "forma_s": d.get("alpha_4"),
            "forma_e": d.get("alpha_5"), "forma_o": d.get("alpha_6"),
            "comentarios": d.get("multiline_11") or "",
            "lat": lat, "lon": lon,
            "fotos": _fotos_de_item(d),
        })

    fecha = (sub.get("datepicker_1") or sub.get("submissionTimeStamp") or "")[:10]
    info = {
        "tipo_inspeccion": "DCVG",
        "contratista": sub.get("alpha_1"),
        "cliente": _v(sub.get("listpicker_1")),
        "tramo": (sub.get("alpha_2") or "").strip() or None,   # Troncal o ramal inspeccionado
        "fecha": fecha,
        "submissionId": sub.get("submissionId"),
        "formName": sub.get("formName"),
        "conteos": {
            "postes": len(postes), "hallazgos": len(hallazgos),
            "hallazgos_simples": len(hallazgos_simples),
            "resistividades": len(resistividades), "defectos": len(defectos),
        },
    }
    return {
        "info": info,
        "postes": postes,
        "hallazgos": hallazgos,
        "hallazgos_simples": hallazgos_simples,
        "resistividades": resistividades,
        "defectos": defectos,
    }


# Mapa formId -> (tipo, funcion_transform).  Completar con los ids reales.
FORM_MAP = {
    "1199286": ("PAP", pap_submission),               # Inspeccion PAP-PBI
    "1240049": ("AISLAMIENTOS", aislamientos_submission),  # Aislamientos..
    "1160295": ("DCVG", dcvg_submission),             # "Inspección DCVG" (form completo: postes+hallazgos+resistividades+defectos)
}
