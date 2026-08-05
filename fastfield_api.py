"""Cliente de la API REST v3 de FastField Forms.

Auth + descarga de media están tomados de una implementación PROBADA del usuario
(no cambiar los headers: la API key va en 'FastField-API-Key', y la foto requiere
2 llamadas: pedir downloadUrl y luego bajar de esa URL firmada).

FastField llama a los envíos de formulario "Form Results". El polling usa:
  - GET /forms           -> lista de formularios (para sus IDs)
  - GET /forms/{id}/results (o /results) -> resultados/envíos de un formulario
  - GET /media/download?key=<archivo> -> URL firmada de una foto
"""
from __future__ import annotations

import base64
import requests

BASE_URL = "https://api.fastfieldforms.com/services/v3"
TIMEOUT = 30


# ── Auth (código probado del usuario) ────────────────────────────────────────
def _basic_auth_header(email, password):
    token = base64.b64encode(f"{email}:{password}".encode()).decode()
    return f"Basic {token}"


def _base_headers(api_key):
    h = {"Cache-Control": "no-cache"}
    if api_key:
        h["FastField-API-Key"] = api_key
    return h


def authenticate(email, password, org_id="", subscription_key=""):
    """Devuelve el sessionToken."""
    headers = {**_base_headers(subscription_key),
               "Authorization": _basic_auth_header(email, password)}
    if org_id:
        headers["X-Gatekeeper-OrgId"] = org_id
    r = requests.post(f"{BASE_URL}/authenticate", headers=headers, timeout=TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"FastField auth falló ({r.status_code}): {r.text[:300]}")
    return r.json()["sessionToken"]


def _auth_headers(session_token, subscription_key):
    return {**_base_headers(subscription_key),
            "X-Gatekeeper-SessionToken": session_token}


# ── Fotos / media (código probado del usuario) ───────────────────────────────
def get_photo_bytes(filename, session_token, subscription_key=""):
    """Descarga una foto por su nombre de archivo (2 llamadas)."""
    r = requests.get(f"{BASE_URL}/media/download", params={"key": filename},
                     headers=_auth_headers(session_token, subscription_key),
                     timeout=TIMEOUT)
    if r.status_code != 200:
        return None
    url = r.json().get("downloadUrl", "")
    if not url:
        return None
    img = requests.get(url, timeout=TIMEOUT)
    return img.content if img.status_code == 200 else None


# ── Formularios y resultados (envíos) ────────────────────────────────────────
def get_forms(session_token, subscription_key=""):
    """Lista los formularios de la cuenta (para conocer sus IDs y nombres)."""
    r = requests.get(f"{BASE_URL}/forms",
                     headers=_auth_headers(session_token, subscription_key),
                     timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def get_form_result(session_token, submission_id, subscription_key=""):
    """Trae UN envío (submission) por su id -> JSON del formulario enviado.
    Endpoint real: GET /formresults/submission/{submissionId}
    NOTA: la API NO tiene un endpoint para LISTAR submissions; solo se obtiene
    por id. Por eso la integración es por WEBHOOK (FastField avisa cada envío
    con su submissionId) y luego se llama a esta función.
    """
    r = requests.get(f"{BASE_URL}/formresults/submission/{submission_id}",
                     headers=_auth_headers(session_token, subscription_key),
                     timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()
