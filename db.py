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
_BUCKET_CARGAS = "cargas"


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


_CLIENTES = {}                       # cache de clientes (reusa conexiones HTTP)


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
    cli = _CLIENTES.get((url, key))
    if cli is None:
        from supabase import create_client   # import perezoso (tras validar config)
        cli = _CLIENTES[(url, key)] = create_client(url, key)
    return cli


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
def _puntos_cips_filas(insp_id, cips):
    """Filas de `puntos_cips` a partir de los dicts CIPS del generador.
    Pura: no toca red. `revision.cips_desde_filas` es su inversa."""
    filas = []
    for i, c in enumerate(cips, 1):
        off = (_f(c.get("off_limpio")) if c.get("off_limpio") is not None
               else _f(c.get("off_mv")))
        filas.append({
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
    return filas


def guardar_inspeccion_cips(info: dict, cips: list, hallazgos: list,
                            tramos: list | None = None,
                            excel_bytes: bytes | None = None,
                            excel_nombre: str | None = None,
                            ppm_bytes: bytes | None = None,
                            ppm_nombre: str | None = None,
                            creado_por: str = "PCC",
                            carga_id: str | None = None,
                            contexto: dict | None = None,
                            revision: str = "A",
                            reemplaza_id: str | None = None) -> str:
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

    insp_id = _crear_o_reemplazar(
        cli,
        _fila_inspeccion(info, "CIPS", abscisa_ini, abscisa_fin, resumen,
                         creado_por, carga_id, contexto, revision,
                         reemplaza=bool(reemplaza_id)),
        "CIPS", reemplaza_id)

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
    _insert_lotes(cli, "puntos_cips", _puntos_cips_filas(insp_id, cips))

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
def listar_inspecciones(tipo: str | None = "CIPS", estado: str | None = None,
                        revisor: bool = False) -> list[dict]:
    """Lista inspecciones. Con revisor=True usa service_role (ve todas, incluidas
    'en_revision'); si no, usa anon y la RLS limita a las aprobadas."""
    cli = _client(write=revisor)
    q = cli.table("inspecciones").select(
        "id, tipo, gasoducto, tramo, fecha, inspector, ot, ciclo, "
        "abscisa_ini, abscisa_fin, resumen, excel_path, ppm_path, "
        "estado, revisado_por, nota_revision, creado_en"
    ).order("creado_en", desc=True)
    if tipo:
        q = q.eq("tipo", tipo)
    if estado:
        q = q.eq("estado", estado)
    return q.execute().data or []


def borrar_inspeccion(insp_id: str):
    """Elimina una inspección: sus puntos/hallazgos/defectos se van por el
    `on delete cascade` del esquema, pero los archivos del bucket NO, así que
    se borran aquí para no dejar huérfanos. Irreversible: respalda antes."""
    cli = _client(write=True)
    r = (cli.table("inspecciones").select("excel_path,ppm_path")
         .eq("id", insp_id).limit(1).execute().data)
    rutas = [p for p in ((r[0].get("excel_path"), r[0].get("ppm_path")) if r
                         else ()) if p]
    if rutas:
        try:
            cli.storage.from_(_BUCKET).remove(rutas)
        except Exception:
            pass                      # el archivo ya no estaba: sigue con la fila
    cli.table("inspecciones").delete().eq("id", insp_id).execute()
    return True


def aprobar_inspeccion(insp_id: str, revisor: str = "PCC"):
    _client(write=True).table("inspecciones").update(
        {"estado": "aprobada", "revisado_por": revisor,
         "revisado_en": _dt.datetime.utcnow().isoformat(), "nota_revision": None}
    ).eq("id", insp_id).execute()


def _obs_filas(insp_id, observaciones):
    """Normaliza y ata a la inspección las observaciones de un rechazo.
    Pura: `revision.normalizar` valida la categoría y lanza ValueError."""
    import revision
    return [dict(revision.normalizar(o), inspeccion_id=insp_id)
            for o in (observaciones or [])]


def rechazar_inspeccion(insp_id: str, revisor: str = "PCC", nota: str = "",
                        observaciones: list | None = None):
    """Rechaza una inspección. `observaciones` es la lista estructurada que el
    generador usa para enrutar la corrección; `nota` queda como resumen legible
    (es lo que el portal ya mostraba)."""
    filas = _obs_filas(insp_id, observaciones)      # valida ANTES de escribir
    cli = _client(write=True)
    if not nota and filas:
        import revision
        nota = " · ".join(
            f"{revision.etiqueta(f['categoria'])}: {f['nota'] or ''}".strip(" :")
            for f in filas)
    cli.table("inspecciones").update(
        {"estado": "rechazada", "revisado_por": revisor,
         "revisado_en": _dt.datetime.utcnow().isoformat(),
         "nota_revision": nota or None}
    ).eq("id", insp_id).execute()
    if filas:
        _insert_lotes(cli, "observaciones_revision", filas)


def observaciones_de(insp_id: str, estado: str | None = "abierta") -> list[dict]:
    """Observaciones de un rechazo, las más viejas primero."""
    q = (_client(write=True).table("observaciones_revision").select("*")
         .eq("inspeccion_id", insp_id).order("creado_en"))
    if estado:
        q = q.eq("estado", estado)
    return q.execute().data or []


def listar_rechazadas(tipo: str | None = None) -> list[dict]:
    """Inspecciones rechazadas pendientes de corregir (buzón del generador)."""
    q = (_client(write=True).table("inspecciones")
         .select("id, tipo, tramo, fecha, inspector, ot, revision, "
                 "nota_revision, revisado_en, carga_id, contexto, excel_path")
         .eq("estado", "rechazada").order("revisado_en", desc=True))
    if tipo:
        q = q.eq("tipo", tipo)
    return q.execute().data or []


def marcar_observaciones(insp_id: str, estado: str = "resuelta"):
    """Cierra las observaciones abiertas de una inspección ya corregida."""
    _client(write=True).table("observaciones_revision").update(
        {"estado": estado}).eq("inspeccion_id", insp_id).eq(
        "estado", "abierta").execute()


def cargar_inspeccion_cips(insp_id: str, write: bool = False) -> dict:
    cli = _client(write=write)
    insp = cli.table("inspecciones").select("*").eq("id", insp_id).single().execute().data
    puntos = (cli.table("puntos_cips").select("*")
              .eq("inspeccion_id", insp_id).order("abscisa").execute().data) or []
    hall = (cli.table("hallazgos").select("*")
            .eq("inspeccion_id", insp_id).order("abscisa_ini").execute().data) or []
    tramos = (cli.table("tramos_no_inspeccionados").select("*")
              .eq("inspeccion_id", insp_id).order("abscisa_ini").execute().data) or []
    return {"inspeccion": insp, "puntos": puntos, "hallazgos": hall, "tramos": tramos}


def url_descarga(path: str, expira_seg: int = 3600, write: bool = False) -> str | None:
    """URL firmada temporal para descargar un archivo del bucket."""
    if not path:
        return None
    cli = _client(write=write)
    try:
        r = cli.storage.from_(_BUCKET).create_signed_url(path, expira_seg)
        return r.get("signedURL") or r.get("signedUrl")
    except Exception:
        return None


# ── Helpers compartidos para publicar (PAP / DCVG) ──────────────────────────
def _subir_excel(cli, insp_id, excel_bytes, excel_nombre, ppm_bytes, ppm_nombre):
    xlsx = ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    excel_path = ppm_path = None
    if excel_bytes:
        excel_path = f"{insp_id}/{excel_nombre or 'informe.xlsx'}"
        cli.storage.from_(_BUCKET).upload(
            excel_path, excel_bytes, {"content-type": xlsx, "upsert": "true"})
    if ppm_bytes:
        ppm_path = f"{insp_id}/{ppm_nombre or 'ppm.xlsx'}"
        cli.storage.from_(_BUCKET).upload(
            ppm_path, ppm_bytes, {"content-type": xlsx, "upsert": "true"})
    if excel_path or ppm_path:
        cli.table("inspecciones").update(
            {"excel_path": excel_path, "ppm_path": ppm_path}
        ).eq("id", insp_id).execute()


def _fila_inspeccion(info, tipo, abscisa_ini, abscisa_fin, resumen, creado_por,
                     carga_id=None, contexto=None, revision="A", reemplaza=False):
    """Fila de `inspecciones`. `carga_id` y `contexto` son la trazabilidad que
    permite reabrir el informe en el generador si lo rechazan; `reemplaza`
    devuelve la inspección a revisión al republicar una corrección."""
    fila = {
        "tipo": tipo,
        "gasoducto": info.get("gasoducto"), "tramo": info.get("tramo"),
        "fecha": _fecha(info.get("fecha")), "inspector": info.get("inspector"),
        "ciclo": str(info.get("ciclo") or info.get("cycle") or "") or None,
        "ot": info.get("ot"), "contratista": info.get("contratista"),
        "serial_equipo": info.get("serial_equipo"),
        "tipo_recubrimiento": info.get("tipo_recubrimiento"),
        "diametro": str(info.get("diametro") or "") or None,
        "abscisa_ini": abscisa_ini, "abscisa_fin": abscisa_fin,
        "resumen": resumen, "creado_por": creado_por,
        "revision": revision or "A",
    }
    if carga_id:
        fila["carga_id"] = carga_id
    if contexto:
        fila["contexto"] = contexto
    if reemplaza:
        # Una corrección republicada vuelve a la cola del revisor limpia.
        fila["estado"] = "en_revision"
        fila["nota_revision"] = None
        fila["revisado_por"] = None
        fila["revisado_en"] = None
    return fila


_HIJAS = {
    "CIPS": ("puntos_cips", "hallazgos", "tramos_no_inspeccionados"),
    "PAP": ("puntos_pap", "hallazgos"),
    "DCVG": ("postes_dcvg", "defectos_dcvg", "resistividades_dcvg", "hallazgos"),
}


def _crear_o_reemplazar(cli, fila, tipo, reemplaza_id=None):
    """Inserta una inspección nueva, o —si es una corrección— actualiza la fila
    existente y borra sus filas hijas para que se reescriban. Actualizar en
    sitio evita que el portal acumule un duplicado por cada revisión."""
    if not reemplaza_id:
        return cli.table("inspecciones").insert(fila).execute().data[0]["id"]
    cli.table("inspecciones").update(fila).eq("id", reemplaza_id).execute()
    for tabla in _HIJAS.get(tipo, ()):
        cli.table(tabla).delete().eq("inspeccion_id", reemplaza_id).execute()
    return reemplaza_id


def _hallazgos_filas(insp_id, hallazgos):
    hs = []
    for i, h in enumerate(hallazgos or [], 1):
        hs.append({
            "inspeccion_id": insp_id, "item": i,
            "abscisa_ini": _i(h.get("abscisa_val") if h.get("abscisa_val") is not None
                              else h.get("abscisa_inicio")),
            "abscisa_fin": _i(h.get("abscisa_fin")), "longitud_m": _f(h.get("longitud")),
            "lat_ini": _f(h.get("lat") if h.get("lat") is not None else h.get("lat_inicio")),
            "lon_ini": _f(h.get("lon") if h.get("lon") is not None else h.get("lon_inicio")),
            "lat_fin": _f(h.get("lat_fin")), "lon_fin": _f(h.get("lon_fin")),
            "fecha": _fecha(h.get("fecha")),
            "tipo": h.get("tipo"), "descripcion": h.get("descripcion"),
        })
    return hs


# ── PAP (poste a poste) ─────────────────────────────────────────────────────
def _puntos_pap_filas(insp_id, potenciales):
    """Filas de `puntos_pap`. Pura. Inversa: `revision.pap_desde_filas`."""
    def _absc(p):
        return _i(p.get("abscisa") if p.get("abscisa") is not None else p.get("pk_m"))

    def _off(p):
        return _f(p.get("off_mv") if p.get("off_mv") is not None else p.get("off"))

    def _on(p):
        return _f(p.get("on_mv") if p.get("on_mv") is not None else p.get("on"))

    filas = []
    for i, p in enumerate(potenciales, 1):
        off = _off(p)
        filas.append({
            "inspeccion_id": insp_id, "item": i, "abscisa": _absc(p),
            "fecha": _fecha(p.get("fecha")), "on_mv": _on(p), "off_mv": off,
            "natural_mv": _f(p.get("potencial_natural")),
            "polarizacion_mv": _f(p.get("polarizacion")),
            "vac_mv": _f(p.get("vac")), "ir_on_off": _f(p.get("ir_on_off")),
            "resistencia": _f(p.get("resistencia")),
            "lat": _f(p.get("lat")), "lon": _f(p.get("lon")),
            "ref_geografica": p.get("ref_geografica"),
            "observaciones": p.get("observaciones"), "estado": estado_cp(off),
        })
    return filas


def guardar_inspeccion_pap(info, potenciales, hallazgos,
                           excel_bytes=None, excel_nombre=None,
                           ppm_bytes=None, ppm_nombre=None, creado_por="PCC",
                           carga_id: str | None = None,
                           contexto: dict | None = None,
                           revision: str = "A",
                           reemplaza_id: str | None = None):
    cli = _client(write=True)

    def _absc(p):
        return _i(p.get("abscisa") if p.get("abscisa") is not None else p.get("pk_m"))

    def _off(p):
        return _f(p.get("off_mv") if p.get("off_mv") is not None else p.get("off"))

    def _on(p):
        return _f(p.get("on_mv") if p.get("on_mv") is not None else p.get("on"))

    offs = [_off(p) for p in potenciales]
    con_dato = [o for o in offs if o is not None]
    cumple = sum(1 for o in con_dato if o <= -850)
    absc = [_absc(p) for p in potenciales if _absc(p) is not None]
    a_ini, a_fin = (min(absc), max(absc)) if absc else (None, None)
    resumen = {
        "total": len(potenciales), "con_dato": len(con_dato), "cumple_850": cumple,
        "pct_cumple": round(100 * cumple / len(con_dato), 1) if con_dato else 0.0,
        "n_hallazgos": len(hallazgos or []),
        "longitud_m": (a_fin - a_ini) if (a_ini is not None and a_fin is not None) else None,
    }
    insp_id = _crear_o_reemplazar(
        cli,
        _fila_inspeccion(info, "PAP", a_ini, a_fin, resumen, creado_por,
                         carga_id, contexto, revision,
                         reemplaza=bool(reemplaza_id)),
        "PAP", reemplaza_id)
    _subir_excel(cli, insp_id, excel_bytes, excel_nombre, ppm_bytes, ppm_nombre)

    _insert_lotes(cli, "puntos_pap", _puntos_pap_filas(insp_id, potenciales))
    _insert_lotes(cli, "hallazgos", _hallazgos_filas(insp_id, hallazgos))
    return insp_id


# ── DCVG (defectos + postes + resistividad) ─────────────────────────────────
def _severidad_dcvg(postes, defectos):
    """Calcula P/RE (interpolado entre postes con pulso), %IR y clasificación
    para cada defecto — misma lógica que generator.fill_dcvg.
    Devuelve lista paralela a `defectos` de dicts {p_re, severidad_pct, clasificacion}."""
    pulsos = sorted(
        [(_f(p.get("pk_m")), abs(_f(p.get("on")) - _f(p.get("off"))))
         for p in postes
         if p.get("pk_m") is not None and _f(p.get("on")) is not None
         and _f(p.get("off")) is not None],
        key=lambda t: t[0])

    def _pre(a):
        if a is None or not pulsos:
            return None
        antes = [t for t in pulsos if t[0] <= a]
        despues = [t for t in pulsos if t[0] >= a]
        if antes and despues:
            da, pa = antes[-1]
            ds, ps = despues[0]
            if ds == da:
                return pa
            return (ps - pa) / (ds - da) * (a - da) + pa
        if antes:
            return antes[-1][1]
        if despues:
            return despues[0][1]
        return None

    def _clas(pct):
        if pct is None:
            return None
        if pct <= 15:
            return "Muy Pequeño"
        if pct <= 35:
            return "Pequeño"
        if pct <= 60:
            return "Mediano"
        return "Grande"

    out = []
    for d in defectos:
        a = _f(d.get("pk_m"))
        pre = _pre(a)
        olre = _f(d.get("ol_re"))
        pct = round(olre / pre * 100, 1) if (olre is not None and pre) else None
        out.append({"p_re": pre, "severidad_pct": pct, "clasificacion": _clas(pct)})
    return out


def _postes_dcvg_filas(insp_id, postes):
    """Filas de `postes_dcvg`. Pura. Inversa: `revision.postes_desde_filas`."""
    return [{
        "inspeccion_id": insp_id, "item": i, "abscisa": _i(p.get("pk_m")),
        "tipo": p.get("tipo"), "on_mv": _f(p.get("on")), "off_mv": _f(p.get("off")),
        "vac_mv": _f(p.get("vac")), "resistencia": _f(p.get("resistencia")),
        "lat": _f(p.get("lat")), "lon": _f(p.get("lon")),
    } for i, p in enumerate(postes or [], 1)]


def _defectos_dcvg_filas(insp_id, defectos, sev):
    """Filas de `defectos_dcvg`. `sev` viene de `_severidad_dcvg` (derivados).
    Pura. Inversa: `revision.defectos_desde_filas` (que NO devuelve derivados)."""
    return [{
        "inspeccion_id": insp_id, "item": i, "abscisa": _i(d.get("pk_m")),
        "sector": d.get("sector"),
        "forma_n": _f(d.get("forma_n")), "forma_e": _f(d.get("forma_e")),
        "forma_s": _f(d.get("forma_s")), "forma_o": _f(d.get("forma_o")),
        "caracter": d.get("caracter"), "ol_re": _f(d.get("ol_re")),
        "p_re": sev[i - 1]["p_re"], "severidad_pct": sev[i - 1]["severidad_pct"],
        "clasificacion": sev[i - 1]["clasificacion"],
        "profundidad": _f(d.get("profundidad")),
        "posicion_reloj": d.get("posicion_reloj"),
        "lat": _f(d.get("lat")), "lon": _f(d.get("lon")),
        "comentarios": d.get("comentarios"),
    } for i, d in enumerate(defectos or [], 1)]


def _resist_dcvg_filas(insp_id, resistividades):
    """Filas de `resistividades_dcvg`. Pura. Inversa: `revision.resist_desde_filas`."""
    return [{
        "inspeccion_id": insp_id, "item": i, "abscisa": _i(r.get("pk_m")),
        "sector": r.get("sector"), "profundidad": _f(r.get("profundidad")),
        "r1": _f(r.get("r1")), "r2": _f(r.get("r2")), "r3": _f(r.get("r3")),
        "lat": _f(r.get("lat")), "lon": _f(r.get("lon")),
    } for i, r in enumerate(resistividades or [], 1)]


def guardar_inspeccion_dcvg(info, postes, defectos, resistividades, hallazgos,
                            excel_bytes=None, excel_nombre=None, creado_por="PCC",
                            carga_id: str | None = None,
                            contexto: dict | None = None,
                            revision: str = "A",
                            reemplaza_id: str | None = None):
    cli = _client(write=True)
    sev = _severidad_dcvg(postes or [], defectos or [])

    todas = ([_i(x.get("pk_m")) for x in (postes or []) + (defectos or [])
              if x.get("pk_m") is not None])
    a_ini, a_fin = (min(todas), max(todas)) if todas else (None, None)
    conteo = {"Muy Pequeño": 0, "Pequeño": 0, "Mediano": 0, "Grande": 0}
    for s in sev:
        if s["clasificacion"] in conteo:
            conteo[s["clasificacion"]] += 1
    resumen = {
        "n_defectos": len(defectos or []), "n_postes": len(postes or []),
        "n_resist": len(resistividades or []), "n_hallazgos": len(hallazgos or []),
        "por_clasificacion": conteo,
        "n_criticos": conteo["Mediano"] + conteo["Grande"],
        "longitud_m": (a_fin - a_ini) if (a_ini is not None and a_fin is not None) else None,
    }
    insp_id = _crear_o_reemplazar(
        cli,
        _fila_inspeccion(info, "DCVG", a_ini, a_fin, resumen, creado_por,
                         carga_id, contexto, revision,
                         reemplaza=bool(reemplaza_id)),
        "DCVG", reemplaza_id)
    _subir_excel(cli, insp_id, excel_bytes, excel_nombre, None, None)

    _insert_lotes(cli, "postes_dcvg", _postes_dcvg_filas(insp_id, postes))
    _insert_lotes(cli, "defectos_dcvg", _defectos_dcvg_filas(insp_id, defectos, sev))
    _insert_lotes(cli, "resistividades_dcvg", _resist_dcvg_filas(insp_id, resistividades))

    _insert_lotes(cli, "hallazgos", _hallazgos_filas(insp_id, hallazgos))
    return insp_id


# ── Cargar detalle PAP / DCVG (portal) ──────────────────────────────────────
def cargar_inspeccion_pap(insp_id, write: bool = False):
    cli = _client(write=write)
    insp = cli.table("inspecciones").select("*").eq("id", insp_id).single().execute().data
    pts = (cli.table("puntos_pap").select("*")
           .eq("inspeccion_id", insp_id).order("abscisa").execute().data) or []
    hall = (cli.table("hallazgos").select("*")
            .eq("inspeccion_id", insp_id).order("abscisa_ini").execute().data) or []
    return {"inspeccion": insp, "puntos": pts, "hallazgos": hall}


def cargar_inspeccion_dcvg(insp_id, write: bool = False):
    cli = _client(write=write)
    insp = cli.table("inspecciones").select("*").eq("id", insp_id).single().execute().data
    postes = (cli.table("postes_dcvg").select("*")
              .eq("inspeccion_id", insp_id).order("abscisa").execute().data) or []
    defectos = (cli.table("defectos_dcvg").select("*")
                .eq("inspeccion_id", insp_id).order("abscisa").execute().data) or []
    resist = (cli.table("resistividades_dcvg").select("*")
              .eq("inspeccion_id", insp_id).order("abscisa").execute().data) or []
    hall = (cli.table("hallazgos").select("*")
            .eq("inspeccion_id", insp_id).order("abscisa_ini").execute().data) or []
    return {"inspeccion": insp, "postes": postes, "defectos": defectos,
            "resistividades": resist, "hallazgos": hall}


# ── Cargas de campo (formulario de técnicos) ────────────────────────────────
def _slug(txt):
    import re as _re
    s = _re.sub(r"[^0-9A-Za-z._-]+", "_", str(txt or "").strip())
    return s.strip("_") or "x"


def guardar_carga(tramo, tipo, fecha, tecnico, archivos_por_categoria, nota=""):
    """Sube al Storage (bucket 'cargas') los archivos de cada categoría y crea la
    fila `cargas`. Además intenta el espejo a SharePoint (si está configurado).

    `archivos_por_categoria`: dict {categoria: [(nombre, bytes), ...]}.
    Devuelve (carga_id, sharepoint_ok, n_archivos)."""
    cli = _client(write=True)
    fecha_s = _fecha(fecha) or "sin_fecha"
    base = f"{_slug(tramo)}/{fecha_s}/{_slug(tipo)}"
    indice = []
    sp_ok = True
    sp_intentos = 0

    try:
        import sharepoint as _sp
        sp_activo = _sp.disponible()
    except Exception:
        sp_activo, _sp = False, None

    for categoria, archivos in (archivos_por_categoria or {}).items():
        for nombre, contenido in archivos:
            path = f"{base}/{_slug(categoria)}/{_slug(nombre)}"
            cli.storage.from_(_BUCKET_CARGAS).upload(
                path, contenido, {"content-type": "application/octet-stream",
                                  "upsert": "true"})
            indice.append({"categoria": categoria, "nombre": nombre,
                           "path": path, "size": len(contenido)})
            if sp_activo:
                sp_intentos += 1
                if not _sp.enviar_archivo(tramo, tipo, fecha_s, tecnico,
                                          categoria, nombre, contenido):
                    sp_ok = False

    sharepoint_ok = bool(sp_activo and sp_intentos and sp_ok)
    fila = {"tramo": tramo, "tipo": tipo, "fecha": _fecha(fecha), "tecnico": tecnico,
            "estado": "pendiente", "archivos": indice, "nota": nota or None,
            "sharepoint_ok": sharepoint_ok}
    carga_id = cli.table("cargas").insert(fila).execute().data[0]["id"]
    return carga_id, sharepoint_ok, len(indice)


def listar_cargas(estado="pendiente"):
    cli = _client(write=True)          # cargas no son visibles al anon (RLS)
    q = cli.table("cargas").select("*").order("creado_en", desc=True)
    if estado:
        q = q.eq("estado", estado)
    return q.execute().data or []


def descargar_carga_archivo(path) -> bytes:
    """Descarga un archivo del bucket de cargas (para la app de procesamiento)."""
    cli = _client(write=True)
    return cli.storage.from_(_BUCKET_CARGAS).download(path)


def url_descarga_carga(path, expira_seg: int = 3600) -> str | None:
    """URL firmada para un archivo del bucket de cargas (sin bajar los bytes)."""
    if not path:
        return None
    cli = _client(write=True)
    try:
        r = cli.storage.from_(_BUCKET_CARGAS).create_signed_url(path, expira_seg)
        return r.get("signedURL") or r.get("signedUrl")
    except Exception:
        return None


def marcar_carga_procesada(carga_id):
    cli = _client(write=True)
    cli.table("cargas").update(
        {"estado": "procesada", "procesada_en": _dt.datetime.utcnow().isoformat()}
    ).eq("id", carga_id).execute()


# ── Cola de FastField (webhook) ──────────────────────────────────────────────
def listar_cola_fastfield(estado="nuevo"):
    """Envíos de FastField pendientes de procesar (los mete la Edge Function)."""
    cli = _client(write=True)          # RLS: solo service_role ve la cola
    q = cli.table("fastfield_cola").select("*").order("recibido_en", desc=True)
    if estado:
        q = q.eq("estado", estado)
    return q.execute().data or []


def guardar_cola_fastfield(submission_id, form_id=None, form_name=None, payload=None):
    """Inserta un envío en la cola (uso manual/pruebas; en prod lo hace el webhook).
    Idempotente: si el submission ya existe, no falla."""
    cli = _client(write=True)
    fila = {"submission_id": str(submission_id), "form_id": form_id,
            "form_name": form_name, "payload": payload}
    try:
        r = cli.table("fastfield_cola").insert(fila).execute()
        return r.data[0]["id"] if r.data else None
    except Exception:
        # ya existe (unique submission_id) -> devolver el existente
        r = (cli.table("fastfield_cola").select("id")
             .eq("submission_id", str(submission_id)).limit(1).execute())
        return r.data[0]["id"] if r.data else None


# ── Históricos por tramo (comparativa) ──────────────────────────────────────
def _mismo_tramo(a, b):
    """¿El histórico es de este tramo? El nombre se escribe distinto en cada
    fuente ('Ansermanuevo' en el informe del contratista, 'Ramal Ansermanuevo'
    en el portal), así que se compara con la normalización de `nombres`
    (sin tildes, sin 'Ramal/Troncal' al frente, sin el 'PK …' del final)."""
    try:
        from nombres import mismo_tramo
        return mismo_tramo(a, b)
    except Exception:                       # sin la tabla de infraestructura
        return (a or "").strip().lower() == (b or "").strip().lower()


def _resumen_historico(puntos):
    offs = [p.get("off") for p in puntos if isinstance(p.get("off"), (int, float))]
    if not offs:
        return {"n": len(puntos), "pct_prot": None, "prom_off": None,
                "min_off": None, "max_off": None, "fuera": None}
    fuera = sum(1 for o in offs if o > -850)
    return {"n": len(offs), "fuera": fuera,
            "pct_prot": round(100 * (len(offs) - fuera) / len(offs), 2),
            "prom_off": round(sum(offs) / len(offs), 1),
            "min_off": round(min(offs), 1), "max_off": round(max(offs), 1)}


def guardar_historico(tramo, tipo, periodo, puntos, fuente=None, fecha=None,
                      resumen=None):
    """Crea el histórico de un tramo.

    `puntos`: [{abscisa, on, off}] en CIPS/PAP; en DCVG cada punto lleva su
    `clase` ('poste' | 'defecto') y, en los defectos, la severidad. Como el
    resumen de DCVG no se calcula sobre potenciales, quien lo lee (historicos.py)
    puede pasarlo hecho en `resumen`."""
    cli = _client(write=True)
    fila = {"tramo": tramo, "tipo": tipo, "periodo": periodo,
            "fecha": _fecha(fecha), "fuente": fuente, "puntos": puntos,
            "resumen": resumen or _resumen_historico(puntos)}
    return cli.table("historicos").insert(fila).execute().data[0]["id"]


def borrar_historico(historico_id):
    """Elimina un histórico (para reemplazarlo por una versión corregida)."""
    cli = _client(write=True)
    cli.table("historicos").delete().eq("id", historico_id).execute()
    return True


def listar_historicos(tramo=None, tipo=None):
    cli = _client(write=True)
    q = cli.table("historicos").select(
        "id,tramo,tipo,periodo,fecha,fuente,resumen,creado_en").order(
        "creado_en", desc=True)
    if tipo:
        q = q.eq("tipo", tipo)
    r = q.execute().data or []
    if tramo:
        r = [h for h in r if _mismo_tramo(h.get("tramo"), tramo)]
    return r


def cargar_historico(historico_id, write: bool = False):
    """Trae un histórico completo (con puntos) por id."""
    cli = _client(write=write)
    r = cli.table("historicos").select("*").eq("id", historico_id).limit(1).execute()
    return r.data[0] if r.data else None


def historico_de_tramo(tramo, tipo="CIPS", write: bool = False):
    """El histórico más reciente de un tramo/tipo (con puntos), o None.

    Se consulta en dos pasos —primero los metadatos de todos, después los
    `puntos` del que casó— porque `puntos` es el 98 % del peso de la tabla y
    bajarlos todos para descartarlos hacía lenta cada carga del dashboard."""
    cli = _client(write=write)
    r = cli.table("historicos").select("id,tramo,tipo,periodo").eq(
        "tipo", tipo).order("creado_en", desc=True).execute()
    for h in (r.data or []):
        if _mismo_tramo(h.get("tramo"), tramo):
            fila = cli.table("historicos").select("*").eq(
                "id", h["id"]).limit(1).execute().data
            return fila[0] if fila else None
    return None


def marcar_cola_fastfield(cola_id, estado, carga_id=None, error=None):
    """estado: 'procesada' | 'error'. Guarda la carga creada o el detalle del error."""
    cli = _client(write=True)
    upd = {"estado": estado, "procesada_en": _dt.datetime.utcnow().isoformat()}
    if carga_id:
        upd["carga_id"] = carga_id
    if error:
        upd["error"] = str(error)[:1000]
    cli.table("fastfield_cola").update(upd).eq("id", cola_id).execute()


# ── Rectificadores (matriz + visor por tramo) ────────────────────────────────
def guardar_rectificador(rect, tramo=None, fuente=None):
    """Inserta un rectificador. `rect` = {plant, placa, nominales, op_data, ...}.
    Devuelve el id creado. El estado/utilización se calculan aquí (rectificadores.py)."""
    import rectificadores as _rx
    cli = _client(write=True)
    placa = rect.get("placa") or {}
    est = _rx.estado_rectificador(rect)
    fila = {
        "tramo": tramo, "tag": placa.get("TAG") or placa.get("ESTRUCTURA"),
        "estructura": placa.get("ESTRUCTURA"), "distrito": rect.get("plant"),
        "fabricante": placa.get("FABRICANTE"), "modelo": placa.get("MODELO"),
        "serial": placa.get("SERIAL"), "estado": est["cls"],
        "payload": rect, "resumen": _rx.resumen_rectificador(rect), "fuente": fuente,
    }
    return cli.table("rectificadores").insert(fila).execute().data[0]["id"]


def listar_rectificadores(tramo=None, write: bool = False):
    """Todos los rectificadores (o los de un tramo). Devuelve filas con `payload`."""
    cli = _client(write=write)
    q = cli.table("rectificadores").select("*")
    if tramo is not None:
        # ilike sin comodines = igualdad sin distinguir mayúsculas, en el servidor
        q = q.ilike("tramo", (tramo or "").strip())
    return q.order("distrito").order("creado_en", desc=True).execute().data or []


def rectificadores_de_tramo(tramo, write: bool = False):
    """Los `payload` de los rectificadores asignados a un tramo (para el dashboard/PDF)."""
    if not tramo:
        return []
    return [x.get("payload") for x in listar_rectificadores(tramo, write=write)
            if x.get("payload")]


def asignar_tramo_rectificador(rect_id, tramo):
    """Asigna (o cambia) el tramo de un rectificador."""
    cli = _client(write=True)
    cli.table("rectificadores").update({"tramo": tramo or None}).eq("id", rect_id).execute()
