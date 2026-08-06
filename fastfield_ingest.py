"""Ingesta de una inspección de FastField -> carga en Supabase.

Flujo (lo dispara la app al drenar `fastfield_cola`):
  1. autenticar en FastField
  2. bajar el envío (JSON) y sus fotos
  3. traducir con FORM_MAP (fastfield_transform)
  4. adaptar a la forma que consume el generador de informes
  5. crear la carga: un `datos.json` (estructurado) + las fotos, estado 'pendiente'

La app de procesamiento luego lee esa carga (rama `fastfield_datos` en
autocargar_carga) y arma el informe.

Credenciales en st.secrets['fastfield'] = {email, password, api_key}
(o variables de entorno FASTFIELD_EMAIL / FASTFIELD_PASSWORD / FASTFIELD_API_KEY).
"""
from __future__ import annotations

import json
import os

import db
import fastfield_api as api
import fastfield_transform as T

try:
    from dcvg_reader import caracter_corto as _caracter_corto
except Exception:
    def _caracter_corto(txt):
        return str(txt or "")

try:
    import streamlit as st
except Exception:
    st = None


# ── Credenciales ─────────────────────────────────────────────────────────────
def _ff_secrets():
    s = {}
    if st is not None:
        try:
            s = dict(st.secrets.get("fastfield", {}))
        except Exception:
            s = {}
    return {
        "email": s.get("email") or os.environ.get("FASTFIELD_EMAIL", ""),
        "password": s.get("password") or os.environ.get("FASTFIELD_PASSWORD", ""),
        "api_key": s.get("api_key") or os.environ.get("FASTFIELD_API_KEY", ""),
    }


def disponible() -> bool:
    c = _ff_secrets()
    return bool(c["email"] and c["password"] and c["api_key"])


# ── Adaptadores: transform -> forma del generador de informes ────────────────
def _num(x):
    try:
        return float(x) if x not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _adaptar_dcvg(res: dict) -> dict:
    """De dcvg_submission() a las claves que usa data[...] en la app.
    (postes/defectos/resist copian la forma de dcvg_reader; hallazgos combinan
    'Hallazgos' + 'Hallazgo simple')."""
    postes = [{
        "tipo": p.get("tipo_poste") or "", "pk_m": p.get("pk_m"),
        "on": p.get("on_mv"), "off": p.get("off_mv"), "vac": p.get("vac"),
        "resistencia": p.get("resistencia"), "lat": p.get("lat"), "lon": p.get("lon"),
    } for p in res.get("postes", [])]

    defectos = [{
        "sector": d.get("sector") or "", "lat": d.get("lat"), "lon": d.get("lon"),
        "pk_m": d.get("pk_m"),
        "forma_n": _num(d.get("forma_n")), "forma_s": _num(d.get("forma_s")),
        "forma_e": _num(d.get("forma_e")), "forma_o": _num(d.get("forma_o")),
        "ol_re": d.get("ol_re"), "profundidad": d.get("profundidad_m"),
        "clasificacion_campo": d.get("clasificacion") or "",
        "posicion_reloj": d.get("forma_defecto") or "",
        "comentarios": d.get("comentarios") or "",
        "caracter": _caracter_corto(d.get("caracter")),
    } for d in res.get("defectos", [])]

    resist = [{
        "pk_m": r.get("pk_m"), "sector": r.get("sector") or "",
        "profundidad": r.get("profundidad"), "lat": r.get("lat"), "lon": r.get("lon"),
        "r1": r.get("r_1m"), "r2": r.get("r_2m"), "r3": r.get("r_3m"),
    } for r in res.get("resistividades", [])]

    hallazgos = []
    for h in res.get("hallazgos", []):          # subform_6 (con abscisa inicio/fin)
        tipo = h.get("tipo") or ""
        hallazgos.append({"abscisa_val": h.get("abscisa_inicio"),
                          "observaciones": tipo, "referencia": tipo,
                          "lat": None, "lon": None})
    for h in res.get("hallazgos_simples", []):  # subform_8 (con PK y coordenadas)
        tipo = h.get("tipo") or ""
        hallazgos.append({"abscisa_val": h.get("pk_m"),
                          "observaciones": tipo, "referencia": tipo,
                          "lat": h.get("lat"), "lon": h.get("lon")})

    info = res.get("info", {})
    return {
        "tipo": "DCVG",
        "info": {
            "tramo": info.get("tramo"), "fecha": info.get("fecha"),
            "inspector": info.get("contratista"),   # el form no trae nombre de técnico aparte
            "cliente": info.get("cliente"), "contratista": info.get("contratista"),
        },
        "dcvg_postes": postes, "dcvg_defectos": defectos,
        "dcvg_resist": resist, "dcvg_hallazgos": hallazgos,
    }


_ADAPTADORES = {
    "DCVG": _adaptar_dcvg,
    # "PAP": _adaptar_pap, "AISLAMIENTOS": _adaptar_aisl,  # pendientes
}

# Tipos que NO son data del informe sino ANEXOS (fotos que van al ZIP de
# entrega). Se guardan como carga con las fotos en la categoría indicada, sin
# datos.json de informe.
_ANEXOS = {
    "INTERFASES": {"categoria": "anexo_interfases",
                   "titulo": "Inspección Visual Interfases"},
}


# ── Recolección de fotos ─────────────────────────────────────────────────────
def _fotos_de_resultado(res: dict):
    """Nombres de archivo de foto de todas las secciones (sin repetir)."""
    nombres = []
    for sec in res.values():
        if isinstance(sec, list):
            for item in sec:
                if isinstance(item, dict):
                    for fn in item.get("fotos", []) or []:
                        if fn and fn not in nombres:
                            nombres.append(fn)
    return nombres


# ── Ingesta principal ────────────────────────────────────────────────────────
def procesar_submission(submission_id, form_id=None, descargar_fotos=True):
    """Baja, traduce y crea la carga. Devuelve dict con resultado.

    Lanza RuntimeError con mensaje claro si algo falla (para mostrar en la UI y
    marcar la cola en 'error')."""
    cred = _ff_secrets()
    if not (cred["email"] and cred["password"] and cred["api_key"]):
        raise RuntimeError("Faltan credenciales de FastField en st.secrets['fastfield'].")

    token = api.authenticate(cred["email"], cred["password"],
                             subscription_key=cred["api_key"])
    sub = api.get_form_result(token, str(submission_id), cred["api_key"])

    fid = str(form_id or sub.get("formId") or "")
    if fid not in T.FORM_MAP:
        raise RuntimeError(f"Formulario {fid} ('{sub.get('formName')}') sin "
                           f"transform mapeado todavía.")
    tipo, transform = T.FORM_MAP[fid]
    res = transform(sub)

    # ¿Es un ANEXO (solo fotos al ZIP) o data de informe (adaptador)?
    es_anexo = tipo in _ANEXOS
    if not es_anexo and tipo not in _ADAPTADORES:
        raise RuntimeError(f"Tipo {tipo} sin adaptador a la app todavía.")

    if es_anexo:
        info = res.get("info", {})
        cat_fotos = _ANEXOS[tipo]["categoria"]
        archivos = {}
    else:
        datos = _ADAPTADORES[tipo](res)
        info = datos.get("info", {})
        cat_fotos = "fotos_rf"
        archivos = {"fastfield_datos": [("datos.json",
                    json.dumps(datos, ensure_ascii=False).encode("utf-8"))]}

    tramo = info.get("tramo") or "sin_tramo"
    fecha = info.get("fecha") or ""
    tecnico = info.get("inspector") or info.get("tecnico") or info.get("contratista") or ""

    n_fotos, fallidas = 0, 0
    if descargar_fotos:
        fotos = []
        for fn in _fotos_de_resultado(res):
            b = api.get_photo_bytes(fn, token, cred["api_key"])
            if b:
                fotos.append((fn, b))
                n_fotos += 1
            else:
                fallidas += 1
        if fotos:
            archivos[cat_fotos] = fotos

    nota = f"FastField {tipo} · submission {submission_id}"
    carga_id, sp_ok, n_arch = db.guardar_carga(tramo, tipo, fecha, tecnico,
                                               archivos, nota=nota)
    conteos = (res.get("info", {}) or {}).get("conteos", {})
    return {
        "carga_id": carga_id, "tipo": tipo, "tramo": tramo, "fecha": fecha,
        "n_fotos": n_fotos, "fotos_fallidas": fallidas, "conteos": conteos,
    }
