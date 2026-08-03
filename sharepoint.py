"""Espejo OPCIONAL de archivos a SharePoint (nube de la empresa).

Vía más simple y sin registro de app en Azure: un flujo de Power Automate con
disparador HTTP ("When a HTTP request is received"). El formulario envía cada
archivo (base64) al flujo y este lo guarda en la biblioteca de SharePoint,
creando la ruta tramo/fecha/categoría.

Si no hay `[sharepoint] flow_url` en los Secrets, `disponible()` es False y todo
sigue funcionando solo con Supabase (el espejo se omite silenciosamente).

Cuerpo JSON que recibe el flujo:
    {tramo, tipo, fecha, tecnico, categoria, nombre, contenido_base64}
El flujo decide la carpeta destino (recomendado: /TGI/<tramo>/<fecha>/<categoria>/).
"""
from __future__ import annotations

import base64

try:
    import streamlit as st
except Exception:
    st = None


def _cfg():
    if st is None:
        return {}
    try:
        return st.secrets.get("sharepoint", {})
    except Exception:
        return {}


def disponible() -> bool:
    return bool(_cfg().get("flow_url"))


def enviar_archivo(tramo, tipo, fecha, tecnico, categoria, nombre, contenido: bytes,
                   timeout=60) -> bool:
    """Envía un archivo al flujo de Power Automate. Devuelve True si el flujo
    respondió OK. No lanza: ante error devuelve False (el espejo es best-effort)."""
    url = _cfg().get("flow_url")
    if not url:
        return False
    import requests
    payload = {
        "tramo": tramo or "", "tipo": tipo or "", "fecha": str(fecha or ""),
        "tecnico": tecnico or "", "categoria": categoria or "", "nombre": nombre,
        "contenido_base64": base64.b64encode(contenido).decode(),
    }
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        return 200 <= r.status_code < 300
    except Exception:
        return False
