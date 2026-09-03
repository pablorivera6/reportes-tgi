"""Asistente de Claude para la devolución de informes rechazados.

Dos trabajos, los dos acotados:
  1. `estructurar_nota` — la nota en lenguaje natural del revisor → observaciones
     con categoría y ubicación, que es lo que enruta el buzón.
  2. `proponer_correcciones` — un diff propuesto sobre los datos ya cargados.

La IA PROPONE; el ingeniero firma. Y solo puede proponer sobre metadatos y texto
libre: `ruta_editable` es una LISTA BLANCA, no una lista negra, así que un campo
nuevo nace prohibido. Los datos de medición (potenciales, severidades, abscisas,
coordenadas) quedan fuera por construcción — el informe se entrega a TGI bajo
contrato y si la IA los "arregla" deja de ser defendible.

Sin Streamlit y sin estado: el cliente se inyecta, para poder probar sin red.
"""
from __future__ import annotations

import json
import re

MODELO = "claude-opus-5"
MAX_TOKENS = 8000

#: Único campo de una fila que la IA puede reescribir: texto que escribió una
#: persona en campo. Añadir aquí es una decisión consciente.
CAMPOS_TEXTO = ("observaciones", "descripcion", "comentarios", "ref_geografica",
                "sector", "tipo")

_RE_RUTA = re.compile(
    r"^(?:info\.(?P<campo_info>[a-z_]+)"
    r"|(?P<lista>[a-z_]+)\[(?P<idx>\d+)\]\.(?P<campo>[a-z_]+))$")


class IARevisionError(RuntimeError):
    """La API no respondió algo usable. El flujo manual sigue disponible."""


def ruta_editable(ruta) -> bool:
    """¿La IA puede tocar esta ruta? `info.*` (metadatos) y los campos de texto
    de una fila. Todo lo demás es NO, incluida cualquier ruta malformada."""
    m = _RE_RUTA.match(str(ruta or "").strip())
    if not m:
        return False
    if m.group("campo_info"):
        return True
    return m.group("campo") in CAMPOS_TEXTO


def filtrar_cambios(cambios):
    """Parte los cambios en (permitidos, descartados). Se llama ANTES de
    mostrarlos: el ingeniero no debe ni ver una propuesta sobre un potencial."""
    ok, fuera = [], []
    for c in cambios or []:
        (ok if ruta_editable(c.get("ruta")) else fuera).append(c)
    return ok, fuera


def aplicar_cambios(data, cambios) -> int:
    """Escribe en `data` los cambios que el ingeniero aprobó. Vuelve a filtrar:
    es la última barrera antes de tocar nada. Devuelve cuántos aplicó."""
    n = 0
    for c in cambios or []:
        ruta = str(c.get("ruta") or "").strip()
        if not ruta_editable(ruta):
            continue
        m = _RE_RUTA.match(ruta)
        if m.group("campo_info"):
            data.setdefault("info", {})[m.group("campo_info")] = c.get("valor_despues")
            n += 1
            continue
        filas = data.get(m.group("lista")) or []
        i = int(m.group("idx"))
        if 0 <= i < len(filas):
            filas[i][m.group("campo")] = c.get("valor_despues")
            n += 1
    return n
