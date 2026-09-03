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

import revision as _revision

CATEGORIAS_VALIDAS = _revision.CATEGORIAS

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


# ── Cliente ─────────────────────────────────────────────────────────────────
def disponible(api_key=None) -> bool:
    """¿Se puede llamar a Claude? Sin esto la app funciona igual, a mano."""
    if not api_key:
        return False
    try:
        import anthropic          # noqa: F401
    except Exception:
        return False
    return True


def _cliente(api_key):
    try:
        import anthropic
    except Exception as e:        # el paquete es opcional, como google-generativeai
        raise IARevisionError(
            "El paquete 'anthropic' no está instalado; el asistente queda "
            "desactivado y el flujo manual sigue igual.") from e
    return anthropic.Anthropic(api_key=api_key)


def _json_de(resp):
    """Texto → dict. `output_config.format` garantiza JSON válido, pero una
    negativa o un corte por max_tokens no lo garantizan: por eso se valida."""
    if getattr(resp, "stop_reason", None) == "refusal":
        raise IARevisionError("Claude declinó la solicitud.")
    try:
        texto = next(b.text for b in resp.content if b.type == "text")
        return json.loads(texto)
    except (StopIteration, ValueError, AttributeError) as e:
        raise IARevisionError(f"Respuesta no interpretable: {e}") from e


def _pedir(cliente, api_key, sistema, payload, esquema):
    cli = cliente or _cliente(api_key)
    try:
        resp = cli.messages.create(
            model=MODELO, max_tokens=MAX_TOKENS,
            system=sistema,
            messages=[{"role": "user",
                       "content": json.dumps(payload, ensure_ascii=False,
                                             default=str)}],
            output_config={"format": {"type": "json_schema", "schema": esquema}},
        )
    except IARevisionError:
        raise
    except Exception as e:        # red, credencial, cuota: nunca tumba la app
        raise IARevisionError(f"No se pudo consultar a Claude: {e}") from e
    return _json_de(resp)


# ── 1. La nota del revisor → observaciones estructuradas ────────────────────
_SISTEMA_OBS = """\
Eres el asistente de un ingeniero de protección catódica de PCC Integrity que
revisa informes de inspección del gasoducto TGI (PAP, CIPS y DCVG).

Recibes la nota con la que un revisor rechazó un informe, escrita informalmente.
Devuélvela partida en observaciones concretas. Una observación por problema.

Categorías (elige exactamente una por observación):
- datos_generales: tramo, OT, contrato, inspector, fecha, ciclo, contratista.
- procesamiento: abscisa corrida, tramo o shapefile equivocado, picos de
  potencial, clasificación o severidad mal calculada. Obliga a reprocesar.
- texto_campo: comentarios del técnico, redacción de hallazgos, conclusiones.
- falta_info: falta un archivo, fotos o mediciones que el técnico no subió.

Reglas:
- Las abscisas van en METROS enteros. "K12" o "12+000" es 12000. Si la nota no
  da abscisa, deja null; no la inventes.
- `campo` solo cuando la nota señale uno concreto ("info.tramo",
  "hallazgo.descripcion"); si no, cadena vacía.
- `nota` reformula el problema en una frase clara y accionable, en español.
- No inventes problemas que la nota no menciona.\
"""

_ESQUEMA_OBS = {
    "type": "object",
    "properties": {
        "observaciones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "categoria": {"type": "string",
                                  "enum": list(CATEGORIAS_VALIDAS)},
                    "campo": {"type": "string"},
                    "abscisa_ini": {"type": ["integer", "null"]},
                    "abscisa_fin": {"type": ["integer", "null"]},
                    "nota": {"type": "string"},
                },
                "required": ["categoria", "campo", "abscisa_ini",
                             "abscisa_fin", "nota"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["observaciones"],
    "additionalProperties": False,
}


def estructurar_nota(nota, contexto, api_key=None, cliente=None):
    """Nota en lenguaje natural → lista de observaciones ya normalizadas.
    `cliente` es para los tests; en producción se pasa `api_key`."""
    datos = _pedir(cliente, api_key, _SISTEMA_OBS,
                   {"nota_del_revisor": nota, "informe": contexto}, _ESQUEMA_OBS)
    try:
        return [_revision.normalizar(dict(o, origen="ia"))
                for o in datos.get("observaciones") or []]
    except ValueError as e:
        raise IARevisionError(f"Claude devolvió una categoría inválida: {e}") from e
