"""Capa de persistencia en Supabase para el portal TGI.

- La app de PROCESAMIENTO (PCC) usa el `service_key` para PUBLICAR inspecciones
  (escribe; omite RLS).
- La app PORTAL (TGI) usa el `anon_key` para LEER (solo SELECT por RLS).

Diseñado para no romper si Supabase no está configurado o `supabase` no está
instalado: `disponible()` informa el estado y las funciones lanzan un error claro.
"""
from __future__ import annotations

import datetime as _dt

try:
    import streamlit as st
except Exception:                       # permite importar el módulo sin streamlit
    st = None

from dashboard import estado_cp        # criterio de estado ya testeado

_BUCKET = "informes"


# ── Configuración / cliente ─────────────────────────────────────────────────
def _secrets():
    if st is None:
        return {}
    try:
        return st.secrets.get("supabase", {})
    except Exception:
        return {}


def disponible(write: bool = False) -> bool:
    """¿Hay credenciales para leer (o escribir) en Supabase?"""
    s = _secrets()
    key = "service_key" if write else "anon_key"
    return bool(s.get("url")) and bool(s.get(key))


def _client(write: bool = False):
    s = _secrets()
    url = s.get("url")
    key = s.get("service_key") if write else s.get("anon_key")
    # el portal puede caer al service_key solo si no hay anon (no recomendado)
    if not key and not write:
        key = s.get("service_key")
    if not url or not key:
        raise RuntimeError(
            "Supabase no está configurado. Falta url/"
            + ("service_key" if write else "anon_key")
            + " en st.secrets['supabase'].")
    from supabase import create_client   # import perezoso (tras validar config)
    return create_client(url, key)


# ── Helpers ─────────────────────────────────────────────────────────────────
def _f(v):
    """A float o None."""
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    f = _f(v)
    return int(round(f)) if f is not None else None


def _fecha(v):
    """Normaliza a 'YYYY-MM-DD' o None."""
    if not v:
        return None
    s = str(v).strip()
    if s.lower() in ("nan", "none", ""):
        return None
    return s[:10]                       # recorta hora si viene 'YYYY-MM-DD HH:MM'


# ── Publicar (escritura, app PCC) ───────────────────────────────────────────
def guardar_inspeccion_cips(info: dict, cips: list, hallazgos: list,
                            tramos: list | None = None,
                            excel_bytes: bytes | None = None,
                            excel_nombre: str | None = None,
                            ppm_bytes: bytes | None = None,
                            ppm_nombre: str | None = None,
                            creado_por: str = "PCC") -> str:
    """Publica una inspección CIPS en Supabase. Devuelve el id (uuid)."""
    cli = _client(write=True)

    # KPIs / resumen (mismo criterio del informe: cumplimiento <= -850 mV)
    offs = [(_f(c.get("off_limpio")) if c.get("off_limpio") is not None
             else _f(c.get("off_mv"))) for c in cips]
    con_dato = [o for o in offs if o is not None]
    cumple = sum(1 for o in con_dato if o <= -850)
    absc = [_i(c.get("abscisa_val")) for c in cips if c.get("abscisa_val") is not None]
    abscisa_ini = min(absc) if absc else None
    abscisa_fin = max(absc) if absc else None
    resumen = {
        "total": len(cips),
        "con_dato": len(con_dato),
        "cumple_850": cumple,
        "pct_cumple": round(100 * cumple / len(con_dato), 1) if con_dato else 0.0,
        "n_hallazgos": len(hallazgos or []),
        "n_tramos_no_insp": len(tramos or []),
        "longitud_m": (abscisa_fin - abscisa_ini) if (abscisa_ini is not None
                       and abscisa_fin is not None) else None,
    }

    fila = {
        "tipo": "CIPS",
        "gasoducto": info.get("gasoducto"),
        "tramo": info.get("tramo"),
        "fecha": _fecha(info.get("fecha")),
        "inspector": info.get("inspector"),
        "ciclo": str(info.get("ciclo") or info.get("cycle") or "") or None,
        "ot": info.get("ot"),
        "contratista": info.get("contratista"),
        "serial_equipo": info.get("serial_equipo"),
        "tipo_recubrimiento": info.get("tipo_recubrimiento"),
        "diametro": str(info.get("diametro") or "") or None,
        "abscisa_ini": abscisa_ini,
        "abscisa_fin": abscisa_fin,
        "resumen": resumen,
        "creado_por": creado_por,
    }
    res = cli.table("inspecciones").insert(fila).execute()
    insp_id = res.data[0]["id"]

    # Subir archivos a Storage y guardar rutas
    excel_path = ppm_path = None
    if excel_bytes:
        excel_path = f"{insp_id}/{excel_nombre or 'informe.xlsx'}"
        cli.storage.from_(_BUCKET).upload(
            excel_path, excel_bytes,
            {"content-type": "application/vnd.openxmlformats-officedocument."
                             "spreadsheetml.sheet", "upsert": "true"})
    if ppm_bytes:
        ppm_path = f"{insp_id}/{ppm_nombre or 'ppm.xlsx'}"
        cli.storage.from_(_BUCKET).upload(
            ppm_path, ppm_bytes,
            {"content-type": "application/vnd.openxmlformats-officedocument."
                             "spreadsheetml.sheet", "upsert": "true"})
    if excel_path or ppm_path:
        cli.table("inspecciones").update(
            {"excel_path": excel_path, "ppm_path": ppm_path}
        ).eq("id", insp_id).execute()

    # Puntos CIPS
    puntos = []
    for i, c in enumerate(cips, 1):
        off = _f(c.get("off_limpio")) if c.get("off_limpio") is not None else _f(c.get("off_mv"))
        puntos.append({
            "inspeccion_id": insp_id, "item": i,
            "abscisa": _i(c.get("abscisa_val")), "fecha": _fecha(c.get("fecha")),
            "on_mv": _f(c.get("on_mv")), "off_mv": _f(c.get("off_mv")),
            "on_limpio": _f(c.get("on_limpio")), "off_limpio": _f(c.get("off_limpio")),
            "natural_mv": _f(c.get("natural_mv")),
            "polarizacion_mv": _f(c.get("polarizacion_mv")),
            "vac_mv": _f(c.get("vac_mv")),
            "metal_on": _f(c.get("metal_on")), "metal_off": _f(c.get("metal_off")),
            "lejano_on": _f(c.get("far_on")), "lejano_off": _f(c.get("far_off")),
            "cercano_on": _f(c.get("near_on")), "cercano_off": _f(c.get("near_off")),
            "ir_on_off": _f(c.get("ir_on_off")),
            "lat": _f(c.get("lat")), "lon": _f(c.get("lon")),
            "observaciones": (c.get("observaciones") or c.get("referencia") or None),
            "estado": estado_cp(off),
        })
    _insert_lotes(cli, "puntos_cips", puntos)

    # Hallazgos
    hs = []
    for i, h in enumerate(hallazgos or [], 1):
        hs.append({
            "inspeccion_id": insp_id, "item": i,
            "abscisa_ini": _i(h.get("abscisa_val") if h.get("abscisa_val") is not None
                              else h.get("abscisa_inicio")),
            "abscisa_fin": _i(h.get("abscisa_fin")),
            "longitud_m": _f(h.get("longitud")),
            "lat_ini": _f(h.get("lat") if h.get("lat") is not None else h.get("lat_inicio")),
            "lon_ini": _f(h.get("lon") if h.get("lon") is not None else h.get("lon_inicio")),
            "lat_fin": _f(h.get("lat_fin")), "lon_fin": _f(h.get("lon_fin")),
            "fecha": _fecha(h.get("fecha")),
            "tipo": h.get("tipo"), "descripcion": h.get("descripcion"),
        })
    _insert_lotes(cli, "hallazgos", hs)

    # Tramos no inspeccionados (si no vienen, se derivan de los hallazgos)
    if tramos is None:
        tramos = [h for h in (hallazgos or [])
                  if "no inspeccion" in str(h.get("tipo", "")).lower()
                  or "rocería" in str(h.get("tipo", "")).lower()
                  or "roceria" in str(h.get("tipo", "")).lower()]
    ts = []
    for i, t in enumerate(tramos or [], 1):
        ts.append({
            "inspeccion_id": insp_id, "item": i,
            "abscisa_ini": _i(t.get("abscisa_val") if t.get("abscisa_val") is not None
                              else t.get("abscisa_inicio")),
            "abscisa_fin": _i(t.get("abscisa_fin")),
            "longitud_m": _f(t.get("longitud")),
            "lat_ini": _f(t.get("lat") if t.get("lat") is not None else t.get("lat_inicio")),
            "lon_ini": _f(t.get("lon") if t.get("lon") is not None else t.get("lon_inicio")),
            "lat_fin": _f(t.get("lat_fin")), "lon_fin": _f(t.get("lon_fin")),
            "fecha": _fecha(t.get("fecha")),
            "justificacion": t.get("descripcion") or t.get("justificacion"),
        })
    _insert_lotes(cli, "tramos_no_inspeccionados", ts)

    return insp_id


def _insert_lotes(cli, tabla, filas, tam=500):
    """Inserta en lotes para no exceder límites de payload."""
    for j in range(0, len(filas), tam):
        cli.table(tabla).insert(filas[j:j + tam]).execute()


# ── Leer (portal TGI) ───────────────────────────────────────────────────────
def listar_inspecciones(tipo: str | None = "CIPS") -> list[dict]:
    cli = _client(write=False)
    q = cli.table("inspecciones").select(
        "id, tipo, gasoducto, tramo, fecha, inspector, ot, ciclo, "
        "abscisa_ini, abscisa_fin, resumen, excel_path, ppm_path, creado_en"
    ).order("creado_en", desc=True)
    if tipo:
        q = q.eq("tipo", tipo)
    return q.execute().data or []


def cargar_inspeccion_cips(insp_id: str) -> dict:
    cli = _client(write=False)
    insp = cli.table("inspecciones").select("*").eq("id", insp_id).single().execute().data
    puntos = (cli.table("puntos_cips").select("*")
              .eq("inspeccion_id", insp_id).order("abscisa").execute().data) or []
    hall = (cli.table("hallazgos").select("*")
            .eq("inspeccion_id", insp_id).order("abscisa_ini").execute().data) or []
    tramos = (cli.table("tramos_no_inspeccionados").select("*")
              .eq("inspeccion_id", insp_id).order("abscisa_ini").execute().data) or []
    return {"inspeccion": insp, "puntos": puntos, "hallazgos": hall, "tramos": tramos}


def url_descarga(path: str, expira_seg: int = 3600) -> str | None:
    """URL firmada temporal para descargar un archivo del bucket."""
    if not path:
        return None
    cli = _client(write=False)
    try:
        r = cli.storage.from_(_BUCKET).create_signed_url(path, expira_seg)
        return r.get("signedURL") or r.get("signedUrl")
    except Exception:
        return None
