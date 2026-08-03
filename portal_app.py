"""
Portal TGI — visualización de inspecciones de protección catódica (PCC Integrity).

App SEPARADA de la de procesamiento: solo LEE lo que PCC publica en Supabase y lo
muestra con un dashboard anclado al contenido del informe CIPS. Diseño PCC.

Despliegue: Streamlit Cloud, mismo repo, main file = portal_app.py.
Si no hay Supabase configurado, arranca en MODO DEMOSTRACIÓN con data de ejemplo.
"""
import os
import base64
import math
import random

import pandas as pd
import streamlit as st

from generator import resource_path
from dashboard import COLOR_ESTADO, estado_cp
import db


# ── Marca ────────────────────────────────────────────────────────────────────
def _b64_img(nombre):
    ruta = resource_path(nombre)
    if os.path.exists(ruta):
        with open(ruta, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


_LOGO_BLANCO = _b64_img("logo_white.png")
_ICONO = resource_path("logo.png")

st.set_page_config(page_title="PCC · Portal TGI",
                   page_icon=_ICONO if os.path.exists(_ICONO) else "🗺️",
                   layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
  html, body, .stApp, .stApp * { font-family: Calibri, 'Segoe UI',
    -apple-system, 'Helvetica Neue', sans-serif; }
  .stApp [data-testid="stIconMaterial"] { font-family:'Material Symbols Rounded',
    'Material Symbols Outlined','Material Icons' !important; }
  .stApp { background:#FFFFFF; }
  h2,h3 { color:#C7113A !important; font-weight:700 !important; }
  [data-testid="stSidebar"] > div:first-child { background:#C7113A !important; }
  [data-testid="stSidebar"] * { color:#FFFFFF !important; }
  [data-testid="stSidebar"] hr { border-color:rgba(255,255,255,0.35) !important; }
  .stButton > button { background:#C7113A !important; color:#FFFFFF !important;
    border:none !important; border-radius:6px !important; font-weight:700 !important; }
  .stButton > button:hover { background:#A50E30 !important; }
  [data-testid="stDownloadButton"] > button { background:#FFFFFF !important;
    color:#C7113A !important; border:1.5px solid #C7113A !important;
    border-radius:6px !important; font-weight:700 !important; }
  [data-testid="stMetricValue"] { color:#C7113A; }
  .pcc-hero { background:#C7113A; color:#FFFFFF; border-radius:8px;
    padding:1.1rem 1.6rem; margin-bottom:1rem; display:flex; align-items:center;
    gap:1.2rem; }
  .pcc-hero h1 { margin:0; font-size:1.55rem; font-weight:800; color:#FFF !important; }
  .pcc-hero p { margin:0.15rem 0 0; opacity:0.9; font-size:0.9rem; }
  .pcc-badge { margin-left:auto; background:#FFFFFF; color:#C7113A; font-weight:800;
    font-size:0.8rem; line-height:1.05; border-radius:6px; padding:0.45rem 0.6rem;
    text-align:center; }
  /* Tarjetas de inspección */
  .insp-card { border:1px solid #E5E5E5; border-radius:10px; padding:1rem 1.2rem;
    margin-bottom:0.9rem; background:#FFFFFF; box-shadow:0 1px 3px rgba(0,0,0,0.06); }
  .insp-card h4 { margin:0 0 0.2rem; color:#333 !important; font-size:1.05rem; }
  .insp-meta { color:#666; font-size:0.85rem; margin:0.1rem 0; }
  .chip { display:inline-block; padding:0.15rem 0.55rem; border-radius:999px;
    font-size:0.75rem; font-weight:700; }
  .chip-ok { background:#E5F3EC; color:#1A7A4A; }
  .chip-warn { background:#FDECEC; color:#C7113A; }
  .chip-tipo { background:#C7113A; color:#FFFFFF; font-size:0.7rem; }
  #MainMenu, footer { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

_logo = (f'<img src="data:image/png;base64,{_LOGO_BLANCO}" style="height:44px;">'
         if _LOGO_BLANCO else '')


# ── Candado del portal (cliente TGI) ─────────────────────────────────────────
def _pwd_portal():
    try:
        return str(st.secrets.get("portal", {}).get("password", ""))
    except Exception:
        return ""


def _pwd_revisor():
    try:
        return str(st.secrets.get("portal", {}).get("reviewer_password", ""))
    except Exception:
        return ""


_PWD = _pwd_portal()
_PWD_REV = _pwd_revisor()
if _PWD and not st.session_state.get("portal_ok"):
    st.markdown(f"""<div class="pcc-hero" style="max-width:520px;margin:3rem auto 1rem;">
      {_logo}<div><h1>Portal TGI_</h1>
      <p>Visualización de inspecciones · PCC Integrity</p></div></div>""",
                unsafe_allow_html=True)
    _, c, _ = st.columns([1, 2, 1])
    with c:
        with st.form("portal_login"):
            clave = st.text_input("Contraseña de acceso", type="password")
            if st.form_submit_button("Entrar"):
                import hmac
                if _PWD_REV and hmac.compare_digest(clave, _PWD_REV):
                    st.session_state.portal_ok = True
                    st.session_state.rol = "revisor"
                    st.rerun()
                elif hmac.compare_digest(clave, _PWD):
                    st.session_state.portal_ok = True
                    st.session_state.rol = "tgi"
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta.")
    st.stop()

# rol activo: 'revisor' (ingeniero PCC, ve y aprueba) o 'tgi' (cliente, solo aprobadas)
_ROL = st.session_state.get("rol", "tgi")
_ES_REVISOR = (_ROL == "revisor")


# ── Data de DEMOSTRACIÓN (cuando no hay Supabase) ────────────────────────────
def _demo_puntos(n, seed, desde=(60, 90), sobre=(150, 175)):
    random.seed(seed)
    lat0, lon0 = 4.6380, -75.5700
    out = []
    for i in range(n):
        on = -1500 + random.uniform(-120, 120)
        off = -1000 + random.uniform(-90, 90)
        if desde[0] <= i <= desde[1]:
            off = -780 + random.uniform(-40, 60)
        if sobre[0] <= i <= sobre[1]:
            off = -1280 + random.uniform(-60, 40)
        est = estado_cp(off)
        out.append({
            "abscisa": i * 20, "on_limpio": round(on, 1), "off_limpio": round(off, 1),
            "vac_mv": round(random.uniform(2000, 9000), 0),
            "lat": round(lat0 + i * 0.00035 + math.sin(i / 15) * 0.0006, 6),
            "lon": round(lon0 + i * 0.00028 + math.cos(i / 18) * 0.0006, 6),
            "estado": est, "observaciones": "",
            "natural_mv": None, "polarizacion_mv": round(on - off, 1),
            "ir_on_off": round(on - off, 1),
        })
    return out


def _demo_dataset():
    insp = [
        {"id": "demo-1", "tipo": "CIPS", "gasoducto": "Mariquita – Cali",
         "tramo": "Salento", "fecha": "2026-07-15", "inspector": "J. Pérez",
         "ot": "OT-2026-0142", "ciclo": "On 0.8s / Off 0.2s",
         "abscisa_ini": 0, "abscisa_fin": 4980,
         "resumen": {"total": 250, "con_dato": 250, "pct_cumple": 77.2,
                     "n_hallazgos": 4, "n_tramos_no_insp": 1, "longitud_m": 4980}},
        {"id": "demo-2", "tipo": "CIPS", "gasoducto": "Ballena – Barranca",
         "tramo": "Montañita", "fecha": "2026-06-28", "inspector": "M. Gómez",
         "ot": "OT-2026-0121", "ciclo": "On 0.8s / Off 0.2s",
         "abscisa_ini": 0, "abscisa_fin": 3600,
         "resumen": {"total": 180, "con_dato": 180, "pct_cumple": 91.1,
                     "n_hallazgos": 2, "n_tramos_no_insp": 0, "longitud_m": 3600}},
    ]
    return insp


def _demo_detalle(insp_id):
    if insp_id == "demo-2":
        pts = _demo_puntos(180, 3, desde=(200, 200), sobre=(300, 300))
    else:
        pts = _demo_puntos(250, 7)
    hall = [
        {"abscisa_ini": 900, "tipo": "Cruce", "descripcion": "cruce de vía terciaria",
         "lat_ini": 4.6538, "lon_ini": -75.5579, "longitud_m": None},
        {"abscisa_ini": 1760, "tipo": "Cable de medición partido",
         "descripcion": "cable partido en poste", "lat_ini": 4.6686,
         "lon_ini": -75.5453, "longitud_m": None},
        {"abscisa_ini": 4000, "tipo": "Válvula", "descripcion": "válvula de seccionamiento",
         "lat_ini": 4.7084, "lon_ini": -75.5139, "longitud_m": None},
    ]
    tramos = [{"abscisa_ini": 2400, "abscisa_fin": 2600, "longitud_m": 200,
               "justificacion": "tramo enmontado, sin rocería"}]
    insp = next(i for i in _demo_dataset() if i["id"] == insp_id)
    return {"inspeccion": insp, "puntos": pts, "hallazgos": hall, "tramos": tramos}


# ── Origen de datos: Supabase o demo ─────────────────────────────────────────
_DEMO = not db.disponible(write=False)


def cargar_lista():
    if _DEMO:
        return _demo_dataset()
    # revisor ve TODAS (incl. en revisión); TGI solo aprobadas (RLS)
    return db.listar_inspecciones(None, revisor=_ES_REVISOR)


def cargar_detalle(insp_id, tipo):
    if _DEMO:
        return _demo_detalle(insp_id)
    w = _ES_REVISOR
    if tipo == "PAP":
        return db.cargar_inspeccion_pap(insp_id, write=w)
    if tipo == "DCVG":
        return db.cargar_inspeccion_dcvg(insp_id, write=w)
    return db.cargar_inspeccion_cips(insp_id, write=w)


# ── Normalización de puntos para mapa/gráficas ───────────────────────────────
def _df_puntos(puntos):
    filas = []
    for p in puntos:
        on = p.get("on_limpio") if p.get("on_limpio") is not None else p.get("on_mv")
        off = p.get("off_limpio") if p.get("off_limpio") is not None else p.get("off_mv")
        est = p.get("estado") or estado_cp(off)
        filas.append({
            "abscisa": p.get("abscisa"), "on": on, "off": off,
            "vac": p.get("vac_mv"), "lat": p.get("lat"), "lon": p.get("lon"),
            "estado": est, "color": COLOR_ESTADO.get(est, "#9CA3AF"),
            "observaciones": p.get("observaciones") or "",
        })
    return pd.DataFrame(filas)


def _abscisa_txt(v):
    if v is None:
        return ""
    try:
        v = int(v)
    except (TypeError, ValueError):
        return str(v)
    return f"K {v // 1000:03d}+{v % 1000:03d}"


# ── Barra de revisión/aprobación (solo rol revisor) ──────────────────────────
def _barra_revision(insp):
    estado = insp.get("estado", "aprobada")
    # etiqueta de estado (visible para todos)
    _badge = {"aprobada": ("✅ Aprobada", "#1A7A4A"),
              "en_revision": ("🕓 En revisión", "#F59E0B"),
              "rechazada": ("✋ Rechazada", "#C7113A")}.get(estado, (estado, "#666"))
    st.markdown(f"<span style='background:{_badge[1]}22;color:{_badge[1]};"
                f"padding:.2rem .6rem;border-radius:999px;font-weight:700;"
                f"font-size:.8rem'>{_badge[0]}</span>", unsafe_allow_html=True)
    if insp.get("nota_revision"):
        st.caption(f"Nota de revisión: {insp['nota_revision']}")
    if not _ES_REVISOR or _DEMO:
        return
    if estado == "en_revision":
        st.info("Revisa el dashboard y el informe descargable. Al **aprobar**, "
                "el cliente TGI podrá verlo en el portal.")
        ca, cb, _ = st.columns([1, 1, 3])
        if ca.button("✅ Aprobar y publicar", key=f"apr_{insp['id']}"):
            db.aprobar_inspeccion(insp["id"], revisor="PCC")
            st.session_state.sel = None
            st.session_state.sel_tipo = None
            st.success("Inspección aprobada. Ya es visible para TGI.")
            st.rerun()
        with cb.popover("✋ Rechazar"):
            _nota = st.text_input("Motivo del rechazo", key=f"nota_{insp['id']}")
            if st.button("Confirmar rechazo", key=f"rej_{insp['id']}"):
                db.rechazar_inspeccion(insp["id"], revisor="PCC", nota=_nota)
                st.session_state.sel = None
                st.session_state.sel_tipo = None
                st.rerun()
    elif estado == "rechazada":
        if st.button("↩️ Reabrir para revisión", key=f"reab_{insp['id']}"):
            _client_reabrir(insp["id"])
            st.rerun()
    st.divider()


def _client_reabrir(insp_id):
    # vuelve a 'en_revision' (usa la API de db con update directo)
    try:
        db._client(write=True).table("inspecciones").update(
            {"estado": "en_revision", "nota_revision": None}).eq("id", insp_id).execute()
    except Exception as e:
        st.error(f"No se pudo reabrir: {e}")


# ── Encabezado común (datos del informe) ─────────────────────────────────────
def _encabezado(insp, subtitulo=""):
    if st.button("← Volver al listado"):
        st.session_state.sel = None
        st.session_state.sel_tipo = None
        st.rerun()
    st.markdown(f"## {insp.get('tramo') or 'Inspección'} · {insp.get('tipo','')}")
    meta = [
        ("Gasoducto", insp.get("gasoducto")), ("Tramo", insp.get("tramo")),
        ("Fecha", insp.get("fecha")), ("Inspector", insp.get("inspector")),
        ("OT", insp.get("ot")), ("Ciclo", insp.get("ciclo")),
        ("Punto inicial", _abscisa_txt(insp.get("abscisa_ini"))),
        ("Punto final", _abscisa_txt(insp.get("abscisa_fin"))),
    ]
    cols = st.columns(4)
    for i, (k, v) in enumerate([m for m in meta if m[1]]):
        cols[i % 4].markdown(f"<div class='insp-meta'><b>{k}</b><br>{v}</div>",
                             unsafe_allow_html=True)
    _barra_revision(insp)
    st.divider()


# ── Render del dashboard CIPS ────────────────────────────────────────────────
def render_dashboard_cips(detalle):
    insp = detalle["inspeccion"]
    dfp = _df_puntos(detalle["puntos"])
    res = insp.get("resumen") or {}

    if st.button("← Volver al listado"):
        st.session_state.sel = None
        st.session_state.sel_tipo = None
        st.rerun()

    st.markdown(f"## {insp.get('tramo') or 'Inspección'} · {insp.get('tipo','CIPS')}")

    # Encabezado (datos del informe)
    meta = [
        ("Gasoducto", insp.get("gasoducto")), ("Tramo", insp.get("tramo")),
        ("Fecha", insp.get("fecha")), ("Inspector", insp.get("inspector")),
        ("OT", insp.get("ot")), ("Ciclo", insp.get("ciclo")),
        ("Punto inicial", _abscisa_txt(insp.get("abscisa_ini"))),
        ("Punto final", _abscisa_txt(insp.get("abscisa_fin"))),
    ]
    cols = st.columns(4)
    for i, (k, v) in enumerate([m for m in meta if m[1]]):
        cols[i % 4].markdown(f"<div class='insp-meta'><b>{k}</b><br>{v}</div>",
                             unsafe_allow_html=True)
    _barra_revision(insp)
    st.divider()

    # KPIs de cumplimiento (criterio -850 mV del informe)
    total = res.get("total", len(dfp))
    pct = res.get("pct_cumple")
    if pct is None and not dfp.empty:
        cd = dfp["off"].dropna()
        pct = round(100 * (cd <= -850).sum() / len(cd), 1) if len(cd) else 0.0
    long_km = (res.get("longitud_m") or 0) / 1000
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Lecturas", total)
    k2.metric("% Cumple ≤ −850 mV", f"{pct:.1f}%" if pct is not None else "—")
    k3.metric("Longitud", f"{long_km:.2f} km" if long_km else "—")
    k4.metric("Hallazgos", res.get("n_hallazgos", len(detalle["hallazgos"])))
    k5.metric("Tramos sin inspeccionar", res.get("n_tramos_no_insp",
                                                  len(detalle["tramos"])))

    # Mapa + Gráfica de potenciales (VDC)
    cmap, cvdc = st.columns([1, 1])
    with cmap:
        st.markdown("**Mapa — estado de protección**")
        mp = dfp.dropna(subset=["lat", "lon"])
        if not mp.empty:
            st.map(mp.rename(columns={"lat": "latitude", "lon": "longitude"}),
                   latitude="latitude", longitude="longitude", color="color", size=8)
            st.caption("🟢 Protegido · 🔴 Desprotegido · 🔵 Sobreprotegido")
        else:
            st.info("Los puntos no tienen coordenadas.")
    with cvdc:
        st.markdown("**Potencial ON/OFF vs abscisa (Gráfica VDC)**")
        _grafica_vdc(dfp)

    # Gráfica VAC (solo si hay data VAC)
    if dfp["vac"].notna().any():
        st.markdown("**Voltaje AC vs abscisa (Gráfica VAC)**")
        _grafica_vac(dfp)

    # Tabla de potenciales
    st.markdown("**Potenciales CIPS**")
    tp = dfp.copy()
    tp["Abscisa"] = tp["abscisa"].apply(_abscisa_txt)
    tp = tp.rename(columns={"on": "ON [mV]", "off": "OFF [mV]", "estado": "Estado",
                            "vac": "VAC [mV]", "observaciones": "Observaciones",
                            "lat": "Latitud", "lon": "Longitud"})
    st.dataframe(tp[["Abscisa", "ON [mV]", "OFF [mV]", "Estado", "VAC [mV]",
                     "Latitud", "Longitud", "Observaciones"]],
                 use_container_width=True, height=280)

    # Hallazgos
    st.markdown("**Hallazgos**")
    if detalle["hallazgos"]:
        dh = pd.DataFrame([{
            "Abscisa inicio": _abscisa_txt(h.get("abscisa_ini")),
            "Abscisa fin": _abscisa_txt(h.get("abscisa_fin")),
            "Longitud [m]": h.get("longitud_m"),
            "Tipo": h.get("tipo"), "Descripción": h.get("descripcion"),
            "Latitud": h.get("lat_ini"), "Longitud°": h.get("lon_ini"),
        } for h in detalle["hallazgos"]])
        st.dataframe(dh, use_container_width=True, height=220)
    else:
        st.caption("Sin hallazgos registrados.")

    # Tramos no inspeccionados
    st.markdown("**Tramos no inspeccionados**")
    if detalle["tramos"]:
        dt = pd.DataFrame([{
            "Abscisa inicio": _abscisa_txt(t.get("abscisa_ini")),
            "Abscisa fin": _abscisa_txt(t.get("abscisa_fin")),
            "Longitud [m]": t.get("longitud_m"),
            "Justificación": t.get("justificacion"),
        } for t in detalle["tramos"]])
        st.dataframe(dt, use_container_width=True, height=160)
    else:
        st.caption("Todo el tramo fue inspeccionado.")

    # Descarga del informe (si está en Storage)
    if not _DEMO and insp.get("excel_path"):
        url = db.url_descarga(insp["excel_path"])
        if url:
            st.link_button("⬇️ Descargar informe (Excel)", url)


def _grafica_vdc(dfp):
    try:
        import plotly.graph_objects as go
        d = dfp.dropna(subset=["abscisa", "off"]).sort_values("abscisa")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=d["abscisa"], y=d["on"], mode="lines",
                      name="ON", line=dict(color="#374151", width=1)))
        fig.add_trace(go.Scatter(x=d["abscisa"], y=d["off"], mode="lines",
                      name="OFF (Instant)", line=dict(color="#C7113A", width=1.5)))
        fig.add_hline(y=-850, line=dict(color="#1A7A4A", dash="dash"),
                      annotation_text="−850 mV")
        fig.add_hline(y=-1200, line=dict(color="#F59E0B", dash="dash"),
                      annotation_text="−1200 mV")
        fig.update_layout(height=340, margin=dict(t=10, b=10, l=10, r=10),
                          xaxis_title="Abscisa [m]", yaxis_title="mV",
                          legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.caption(f"(gráfica no disponible: {e})")


def _grafica_vac(dfp):
    try:
        import plotly.graph_objects as go
        d = dfp.dropna(subset=["abscisa", "vac"]).sort_values("abscisa")
        vac_v = d["vac"] / 1000.0                       # mV -> V
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=d["abscisa"], y=vac_v, mode="lines",
                      name="VAC", line=dict(color="#1F6FEB", width=1.3)))
        fig.add_hline(y=15, line=dict(color="#C7113A", dash="dash"),
                      annotation_text="15 VAC (SP0177)")
        fig.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10),
                          xaxis_title="Abscisa [m]", yaxis_title="V AC",
                          legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.caption(f"(gráfica VAC no disponible: {e})")


# ── Render del dashboard PAP (poste a poste) ─────────────────────────────────
def render_dashboard_pap(detalle):
    insp = detalle["inspeccion"]
    res = insp.get("resumen") or {}
    _encabezado(insp)
    dfp = _df_puntos(detalle["puntos"])

    total = res.get("total", len(dfp))
    pct = res.get("pct_cumple")
    if pct is None and not dfp.empty:
        cd = dfp["off"].dropna()
        pct = round(100 * (cd <= -850).sum() / len(cd), 1) if len(cd) else 0.0
    long_km = (res.get("longitud_m") or 0) / 1000
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Postes medidos", total)
    k2.metric("% Cumple ≤ −850 mV", f"{pct:.1f}%" if pct is not None else "—")
    k3.metric("Longitud", f"{long_km:.2f} km" if long_km else "—")
    k4.metric("Hallazgos", res.get("n_hallazgos", len(detalle["hallazgos"])))

    cmap, cpot = st.columns([1, 1])
    with cmap:
        st.markdown("**Mapa — estado de protección**")
        mp = dfp.dropna(subset=["lat", "lon"])
        if not mp.empty:
            st.map(mp.rename(columns={"lat": "latitude", "lon": "longitude"}),
                   latitude="latitude", longitude="longitude", color="color", size=8)
            st.caption("🟢 Protegido · 🔴 Desprotegido · 🔵 Sobreprotegido")
        else:
            st.info("Los postes no tienen coordenadas.")
    with cpot:
        st.markdown("**Potencial ON/OFF por poste vs abscisa**")
        _grafica_potenciales_pap(dfp)

    st.markdown("**Potenciales PAP**")
    tp = dfp.copy()
    tp["Abscisa"] = tp["abscisa"].apply(_abscisa_txt)
    tp = tp.rename(columns={"on": "ON [mV]", "off": "OFF [mV]", "estado": "Estado",
                            "observaciones": "Observaciones", "lat": "Latitud",
                            "lon": "Longitud"})
    st.dataframe(tp[["Abscisa", "ON [mV]", "OFF [mV]", "Estado",
                     "Latitud", "Longitud", "Observaciones"]],
                 use_container_width=True, height=300)

    st.markdown("**Hallazgos**")
    _tabla_hallazgos(detalle["hallazgos"])
    _descarga_informe(insp)


def _grafica_potenciales_pap(dfp):
    try:
        import plotly.graph_objects as go
        d = dfp.dropna(subset=["abscisa", "off"]).sort_values("abscisa")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=d["abscisa"], y=d["on"], mode="lines+markers",
                      name="ON", line=dict(color="#374151", width=1),
                      marker=dict(size=5)))
        fig.add_trace(go.Scatter(x=d["abscisa"], y=d["off"], mode="lines+markers",
                      name="OFF", line=dict(color="#C7113A", width=1.5),
                      marker=dict(size=5)))
        fig.add_hline(y=-850, line=dict(color="#1A7A4A", dash="dash"),
                      annotation_text="−850 mV")
        fig.add_hline(y=-1200, line=dict(color="#F59E0B", dash="dash"),
                      annotation_text="−1200 mV")
        fig.update_layout(height=340, margin=dict(t=10, b=10, l=10, r=10),
                          xaxis_title="Abscisa [m]", yaxis_title="mV",
                          legend=dict(orientation="h", y=-0.25))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.caption(f"(gráfica no disponible: {e})")


# ── Render del dashboard DCVG (defectos + resistividad) ──────────────────────
COLOR_CLAS = {"Muy Pequeño": "#1A7A4A", "Pequeño": "#84B84C",
              "Mediano": "#F59E0B", "Grande": "#C7113A"}


def render_dashboard_dcvg(detalle):
    insp = detalle["inspeccion"]
    res = insp.get("resumen") or {}
    _encabezado(insp)

    dfd = pd.DataFrame(detalle["defectos"])
    conteo = res.get("por_clasificacion") or {}
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Defectos", res.get("n_defectos", len(dfd)))
    k2.metric("Críticos (Med+Gr)", res.get("n_criticos",
              (conteo.get("Mediano", 0) + conteo.get("Grande", 0))))
    k3.metric("Postes", res.get("n_postes", len(detalle["postes"])))
    k4.metric("Resistividades", res.get("n_resist", len(detalle["resistividades"])))
    k5.metric("Hallazgos", res.get("n_hallazgos", len(detalle["hallazgos"])))

    # distribución por clasificación (severidad del informe)
    if conteo:
        st.markdown("**Distribución de defectos por severidad**")
        cc = st.columns(4)
        for i, clas in enumerate(["Muy Pequeño", "Pequeño", "Mediano", "Grande"]):
            cc[i].markdown(
                f"<div class='insp-meta'><b style='color:{COLOR_CLAS[clas]}'>"
                f"● {clas}</b><br><span style='font-size:1.4rem'>"
                f"{conteo.get(clas, 0)}</span></div>", unsafe_allow_html=True)
        st.divider()

    cmap, csev = st.columns([1, 1])
    with cmap:
        st.markdown("**Mapa — defectos por severidad**")
        if not dfd.empty and dfd[["lat", "lon"]].notna().all(axis=1).any():
            mp = dfd.dropna(subset=["lat", "lon"]).copy()
            mp["color"] = mp["clasificacion"].map(COLOR_CLAS).fillna("#9CA3AF")
            st.map(mp.rename(columns={"lat": "latitude", "lon": "longitude"}),
                   latitude="latitude", longitude="longitude", color="color", size=10)
            st.caption("🟢 Muy pequeño · 🟩 Pequeño · 🟧 Mediano · 🔴 Grande")
        else:
            st.info("Los defectos no tienen coordenadas.")
    with csev:
        st.markdown("**Severidad %IR vs abscisa**")
        _grafica_severidad_dcvg(dfd)

    # resistividad del suelo
    if detalle["resistividades"]:
        st.markdown("**Resistividad del suelo vs abscisa**")
        _grafica_resistividad(pd.DataFrame(detalle["resistividades"]))

    # tabla de defectos (Inspección DCVG)
    st.markdown("**Defectos**")
    if not dfd.empty:
        td = dfd.copy()
        td["Abscisa"] = td["abscisa"].apply(_abscisa_txt)
        td = td.rename(columns={
            "caracter": "Carácter", "ol_re": "OL/RE [mV]", "p_re": "P/RE [mV]",
            "severidad_pct": "Severidad %IR", "clasificacion": "Clasificación",
            "profundidad": "Profundidad", "posicion_reloj": "Posición reloj",
            "comentarios": "Comentarios"})
        cols = ["Abscisa", "Carácter", "OL/RE [mV]", "P/RE [mV]", "Severidad %IR",
                "Clasificación", "Profundidad", "Posición reloj", "Comentarios"]
        st.dataframe(td[[c for c in cols if c in td.columns]],
                     use_container_width=True, height=300)
    else:
        st.caption("Sin defectos registrados.")

    # tabla de resistividades
    if detalle["resistividades"]:
        st.markdown("**Resistividades (Wenner 1/2/3 m)**")
        tr = pd.DataFrame(detalle["resistividades"])
        tr["Abscisa"] = tr["abscisa"].apply(_abscisa_txt)
        tr = tr.rename(columns={"r1": "1 m [Ω·m]", "r2": "2 m [Ω·m]",
                                "r3": "3 m [Ω·m]", "sector": "Sector"})
        st.dataframe(tr[[c for c in ["Abscisa", "Sector", "1 m [Ω·m]", "2 m [Ω·m]",
                         "3 m [Ω·m]"] if c in tr.columns]],
                     use_container_width=True, height=200)

    st.markdown("**Hallazgos**")
    _tabla_hallazgos(detalle["hallazgos"])
    _descarga_informe(insp)


def _grafica_severidad_dcvg(dfd):
    try:
        import plotly.graph_objects as go
        if dfd.empty or dfd["severidad_pct"].dropna().empty:
            st.caption("Sin datos de severidad.")
            return
        d = dfd.dropna(subset=["abscisa", "severidad_pct"]).sort_values("abscisa")
        colors = d["clasificacion"].map(COLOR_CLAS).fillna("#9CA3AF")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=d["abscisa"], y=d["severidad_pct"],
                      marker_color=list(colors), name="Severidad %IR",
                      width=[15] * len(d)))
        for y, txt, col in [(15, "15%", "#84B84C"), (35, "35%", "#F59E0B"),
                            (60, "60%", "#C7113A")]:
            fig.add_hline(y=y, line=dict(color=col, dash="dash"),
                          annotation_text=txt)
        fig.update_layout(height=340, margin=dict(t=10, b=10, l=10, r=10),
                          xaxis_title="Abscisa [m]", yaxis_title="Severidad %IR",
                          showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.caption(f"(gráfica no disponible: {e})")


def _grafica_resistividad(dfr):
    try:
        import plotly.graph_objects as go
        d = dfr.dropna(subset=["abscisa"]).sort_values("abscisa")
        fig = go.Figure()
        for col, nombre, color in [("r1", "1 m", "#374151"), ("r2", "2 m", "#1F6FEB"),
                                   ("r3", "3 m", "#C7113A")]:
            if col in d.columns and d[col].notna().any():
                fig.add_trace(go.Scatter(x=d["abscisa"], y=d[col], mode="lines+markers",
                              name=nombre, line=dict(color=color, width=1.2),
                              marker=dict(size=5)))
        fig.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10),
                          xaxis_title="Abscisa [m]", yaxis_title="Resistividad [Ω·m]",
                          legend=dict(orientation="h", y=-0.3))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.caption(f"(gráfica resistividad no disponible: {e})")


# ── Utilidades compartidas de render ─────────────────────────────────────────
def _tabla_hallazgos(hallazgos):
    if hallazgos:
        dh = pd.DataFrame([{
            "Abscisa inicio": _abscisa_txt(h.get("abscisa_ini")),
            "Abscisa fin": _abscisa_txt(h.get("abscisa_fin")),
            "Tipo": h.get("tipo"), "Descripción": h.get("descripcion"),
            "Latitud": h.get("lat_ini"), "Longitud": h.get("lon_ini"),
        } for h in hallazgos])
        st.dataframe(dh, use_container_width=True, height=200)
    else:
        st.caption("Sin hallazgos registrados.")


def _descarga_informe(insp):
    if not _DEMO and insp.get("excel_path"):
        url = db.url_descarga(insp["excel_path"], write=_ES_REVISOR)
        if url:
            st.link_button("⬇️ Descargar informe (Excel)", url)


# ── Listado de inspecciones ──────────────────────────────────────────────────
def render_listado():
    st.markdown("## Inspecciones publicadas")
    try:
        lista = cargar_lista()
    except Exception as e:
        st.error(f"No se pudo leer el histórico: {e}")
        return
    if not lista:
        st.info("Aún no hay inspecciones publicadas.")
        return

    # filtros por tipo y tramo
    cf1, cf2 = st.columns(2)
    tipos = sorted({i.get("tipo") for i in lista if i.get("tipo")})
    ft = cf1.selectbox("Tipo de inspección", ["Todos"] + tipos, index=0)
    if ft != "Todos":
        lista = [i for i in lista if i.get("tipo") == ft]
    tramos = sorted({i.get("tramo") for i in lista if i.get("tramo")})
    fx = cf2.selectbox("Tramo", ["Todos"] + tramos, index=0)
    if fx != "Todos":
        lista = [i for i in lista if i.get("tramo") == fx]

    # El revisor puede filtrar por estado (para ver lo que falta aprobar)
    if _ES_REVISOR:
        fe = st.radio("Estado", ["Todas", "🕓 En revisión", "✅ Aprobadas",
                                 "✋ Rechazadas"], horizontal=True, index=0)
        mapa_e = {"🕓 En revisión": "en_revision", "✅ Aprobadas": "aprobada",
                  "✋ Rechazadas": "rechazada"}
        if fe in mapa_e:
            lista = [i for i in lista if i.get("estado") == mapa_e[fe]]
        pend = sum(1 for i in cargar_lista() if i.get("estado") == "en_revision")
        if pend:
            st.warning(f"🕓 {pend} inspección(es) esperando tu aprobación.")

    _EST = {"aprobada": ("✅", "#1A7A4A"), "en_revision": ("🕓", "#F59E0B"),
            "rechazada": ("✋", "#C7113A")}
    for insp in lista:
        res = insp.get("resumen") or {}
        tipo = insp.get("tipo", "CIPS")
        chip, extra = _chips_listado(tipo, res)
        est = insp.get("estado", "aprobada")
        est_chip = ""
        if _ES_REVISOR:
            e = _EST.get(est, ("", "#666"))
            est_chip = (f"<span class='chip' style='background:{e[1]}22;"
                        f"color:{e[1]}'>{e[0]} {est.replace('_',' ')}</span>")
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"""<div class="insp-card">
              <h4><span class="chip chip-tipo">{tipo}</span> &nbsp;
                 {insp.get('tramo','—')} · {insp.get('gasoducto','')} &nbsp; {est_chip}</h4>
              <p class="insp-meta">📅 {insp.get('fecha','—')} &nbsp;·&nbsp;
                 👷 {insp.get('inspector','—')} &nbsp;·&nbsp; OT {insp.get('ot','—')}
                 &nbsp;·&nbsp; {extra} &nbsp; {chip}</p>
            </div>""", unsafe_allow_html=True)
        with c2:
            _lbl = "Revisar" if (_ES_REVISOR and est == "en_revision") else "Ver dashboard"
            if st.button(_lbl, key=f"ver-{insp['id']}"):
                st.session_state.sel = insp["id"]
                st.session_state.sel_tipo = tipo
                st.rerun()


def _chips_listado(tipo, res):
    """Devuelve (chip_estado, texto_extra) según el tipo de inspección."""
    if tipo == "DCVG":
        crit = res.get("n_criticos", 0)
        extra = f"{res.get('n_defectos', '?')} defectos"
        chip = (f"<span class='chip chip-warn'>{crit} críticos</span>" if crit
                else "<span class='chip chip-ok'>Sin críticos</span>")
        return chip, extra
    # CIPS / PAP: cumplimiento -850
    pct = res.get("pct_cumple")
    extra = f"{res.get('total', '?')} lecturas"
    chip = (f"<span class='chip chip-ok'>Cumple {pct:.0f}%</span>"
            if (pct is not None and pct >= 85)
            else f"<span class='chip chip-warn'>Cumple {pct:.0f}%</span>"
            if pct is not None else "")
    return chip, extra


# ── Vista consolidada por tramo (CIPS + PAP + DCVG juntos) ───────────────────
def _off_de_punto(p):
    o = p.get("off_limpio") if p.get("off_limpio") is not None else p.get("off_mv")
    return o if o is not None else p.get("off")


def render_vista_tramo():
    st.markdown("## Vista consolidada por tramo")
    st.caption("Cruza protección catódica (CIPS/PAP) y defectos de recubrimiento "
               "(DCVG) del mismo tramo, alineados por abscisa, para priorizar.")
    try:
        lista = cargar_lista()
    except Exception as e:
        st.error(f"No se pudo leer el histórico: {e}")
        return
    if not lista:
        st.info("Aún no hay inspecciones publicadas.")
        return

    # agrupar por tramo -> tipo -> inspecciones (más recientes primero)
    por_tramo = {}
    for i in lista:
        por_tramo.setdefault(i.get("tramo") or "—", {}).setdefault(i.get("tipo"), []).append(i)
    tramos = sorted(por_tramo)
    tramo = st.selectbox("Tramo", tramos, index=0)
    grupos = por_tramo[tramo]

    # elegir una inspección por tipo (por defecto la más reciente)
    st.markdown("**Inspecciones del tramo**")
    cols = st.columns(3)
    elegidas = {}
    for j, tp in enumerate(["CIPS", "PAP", "DCVG"]):
        insps = sorted(grupos.get(tp, []), key=lambda x: x.get("fecha") or "",
                       reverse=True)
        with cols[j]:
            if insps:
                op = {f"{x.get('fecha','—')} · OT {x.get('ot','—')}": x for x in insps}
                sel = st.selectbox(f"{tp}", list(op.keys()), key=f"vt_{tp}")
                elegidas[tp] = op[sel]
            else:
                st.selectbox(f"{tp}", ["— sin data —"], key=f"vt_{tp}", disabled=True)

    if not elegidas:
        st.info("Este tramo aún no tiene inspecciones para consolidar.")
        return

    # cargar detalles
    det = {}
    if _DEMO:
        for tp, insp in elegidas.items():
            det[tp] = _demo_detalle(insp["id"])
    else:
        for tp, insp in elegidas.items():
            if tp == "CIPS":
                det[tp] = db.cargar_inspeccion_cips(insp["id"])
            elif tp == "PAP":
                det[tp] = db.cargar_inspeccion_pap(insp["id"])
            else:
                det[tp] = db.cargar_inspeccion_dcvg(insp["id"])

    st.divider()
    # KPIs por tipo
    kcols = st.columns(3)
    for j, tp in enumerate(["CIPS", "PAP", "DCVG"]):
        with kcols[j]:
            if tp in elegidas:
                r = elegidas[tp].get("resumen") or {}
                if tp == "DCVG":
                    st.metric(f"{tp} · defectos críticos",
                              r.get("n_criticos", 0),
                              help="Defectos Mediano + Grande")
                else:
                    pct = r.get("pct_cumple")
                    st.metric(f"{tp} · % cumple −850",
                              f"{pct:.0f}%" if pct is not None else "—")
            else:
                st.metric(f"{tp}", "sin data")

    # gráfica alineada por abscisa (potencial arriba, severidad DCVG abajo)
    st.markdown("**Protección vs defectos — alineado por abscisa**")
    _grafica_consolidada(det)

    # mapa combinado
    st.markdown("**Mapa combinado**")
    _mapa_consolidado(det)

    # zonas críticas: desprotegido + defecto DCVG cercano
    st.markdown("**🚩 Zonas críticas** (ducto desprotegido con defecto de recubrimiento)")
    _zonas_criticas(det)


def _grafica_consolidada(det):
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        tiene_dcvg = "DCVG" in det and det["DCVG"]["defectos"]
        filas = 2 if tiene_dcvg else 1
        fig = make_subplots(rows=filas, cols=1, shared_xaxes=True,
                            vertical_spacing=0.08,
                            row_heights=[0.6, 0.4] if tiene_dcvg else [1.0],
                            subplot_titles=(["Potencial OFF (protección)",
                                             "Severidad de defectos DCVG"]
                                            if tiene_dcvg else ["Potencial OFF (protección)"]))
        # CIPS (línea)
        if "CIPS" in det:
            d = pd.DataFrame(det["CIPS"]["puntos"])
            if not d.empty:
                d["off"] = d.apply(_off_de_punto, axis=1)
                d = d.dropna(subset=["abscisa", "off"]).sort_values("abscisa")
                fig.add_trace(go.Scatter(x=d["abscisa"], y=d["off"], mode="lines",
                              name="CIPS OFF", line=dict(color="#C7113A", width=1.3)),
                              row=1, col=1)
        # PAP (marcadores)
        if "PAP" in det:
            d = pd.DataFrame(det["PAP"]["puntos"])
            if not d.empty:
                d["off"] = d.apply(_off_de_punto, axis=1)
                d = d.dropna(subset=["abscisa", "off"]).sort_values("abscisa")
                fig.add_trace(go.Scatter(x=d["abscisa"], y=d["off"], mode="markers",
                              name="PAP OFF", marker=dict(color="#1F6FEB", size=6)),
                              row=1, col=1)
        fig.add_hline(y=-850, line=dict(color="#1A7A4A", dash="dash"), row=1, col=1)
        fig.update_yaxes(title_text="mV", row=1, col=1)
        # DCVG severidad (barras)
        if tiene_dcvg:
            dd = pd.DataFrame(det["DCVG"]["defectos"]).dropna(subset=["abscisa"])
            if "severidad_pct" in dd:
                dd = dd.dropna(subset=["severidad_pct"])
                colores = dd["clasificacion"].map(COLOR_CLAS).fillna("#9CA3AF")
                fig.add_trace(go.Bar(x=dd["abscisa"], y=dd["severidad_pct"],
                              marker_color=list(colores), name="Severidad %IR",
                              width=[15] * len(dd)), row=2, col=1)
                for y, col in [(15, "#84B84C"), (35, "#F59E0B"), (60, "#C7113A")]:
                    fig.add_hline(y=y, line=dict(color=col, dash="dash"), row=2, col=1)
                fig.update_yaxes(title_text="%IR", row=2, col=1)
            fig.update_xaxes(title_text="Abscisa [m]", row=2, col=1)
        else:
            fig.update_xaxes(title_text="Abscisa [m]", row=1, col=1)
        fig.update_layout(height=520 if tiene_dcvg else 340, showlegend=True,
                          margin=dict(t=40, b=10, l=10, r=10),
                          legend=dict(orientation="h", y=-0.12))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.caption(f"(gráfica consolidada no disponible: {e})")


def _mapa_consolidado(det):
    filas = []
    if "CIPS" in det:
        for p in det["CIPS"]["puntos"]:
            est = p.get("estado") or estado_cp(_off_de_punto(p))
            filas.append({"lat": p.get("lat"), "lon": p.get("lon"),
                          "color": COLOR_ESTADO.get(est, "#9CA3AF")})
    if "PAP" in det:
        for p in det["PAP"]["puntos"]:
            est = p.get("estado") or estado_cp(_off_de_punto(p))
            filas.append({"lat": p.get("lat"), "lon": p.get("lon"),
                          "color": COLOR_ESTADO.get(est, "#9CA3AF")})
    if "DCVG" in det:
        for d in det["DCVG"]["defectos"]:
            filas.append({"lat": d.get("lat"), "lon": d.get("lon"),
                          "color": COLOR_CLAS.get(d.get("clasificacion"), "#111111")})
    mp = pd.DataFrame(filas).dropna(subset=["lat", "lon"])
    if not mp.empty:
        st.map(mp.rename(columns={"lat": "latitude", "lon": "longitude"}),
               latitude="latitude", longitude="longitude", color="color", size=7)
        st.caption("Protección 🟢🔴🔵 (CIPS/PAP) · Defectos DCVG 🟩🟧🔴 por severidad")
    else:
        st.info("No hay coordenadas para el mapa combinado.")


def _zonas_criticas(det, umbral_m=25):
    """Defectos DCVG Mediano/Grande cuyo potencial CIPS/PAP más cercano indica
    desprotección (OFF > −850 mV): máxima prioridad de intervención."""
    if "DCVG" not in det or not det["DCVG"]["defectos"]:
        st.caption("No hay defectos DCVG en este tramo para cruzar.")
        return
    # potenciales disponibles (CIPS + PAP) como (abscisa, off)
    pots = []
    for tp in ("CIPS", "PAP"):
        if tp in det:
            for p in det[tp]["puntos"]:
                a, o = p.get("abscisa"), _off_de_punto(p)
                if a is not None and o is not None:
                    pots.append((a, o))
    filas = []
    for d in det["DCVG"]["defectos"]:
        if d.get("clasificacion") not in ("Mediano", "Grande"):
            continue
        a = d.get("abscisa")
        if a is None:
            continue
        cerc = min(pots, key=lambda t: abs(t[0] - a)) if pots else None
        off = cerc[1] if cerc else None
        desprot = off is not None and off > -850
        filas.append({
            "Abscisa": _abscisa_txt(a), "Severidad": d.get("clasificacion"),
            "%IR": d.get("severidad_pct"),
            "OFF cercano [mV]": round(off, 1) if off is not None else None,
            "Estado CP": "Desprotegido" if desprot else (
                "Protegido" if off is not None else "sin dato"),
            "Prioridad": "🔴 ALTA" if desprot else "🟠 Media",
        })
    if not filas:
        st.success("Sin zonas críticas: no hay defectos medianos/grandes en zonas "
                   "desprotegidas.")
        return
    dfz = pd.DataFrame(filas)
    altas = (dfz["Prioridad"] == "🔴 ALTA").sum()
    if altas:
        st.error(f"⚠️ {altas} zona(s) de prioridad ALTA: defecto grande/mediano "
                 f"donde el ducto está desprotegido.")
    st.dataframe(dfz.sort_values("Prioridad"), use_container_width=True, height=240)


# ── App ──────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"<div style='text-align:center'>{_logo}<br>"
                "<b>Portal TGI</b><br><span style='opacity:.85'>fits you_</span></div>",
                unsafe_allow_html=True)
    st.divider()
    if _DEMO:
        st.warning("Modo demostración\n\nSupabase no configurado: se muestra data "
                   "de ejemplo.", icon="⚠️")
    else:
        st.success("Conectado al histórico", icon="✅")
    if _ES_REVISOR:
        st.info("👷 Rol: **Revisor PCC**\n\nVes también las inspecciones en "
                "revisión y puedes aprobarlas.", icon="🛠️")
    if st.session_state.get("portal_ok") and st.button("Salir"):
        for k in ("portal_ok", "rol", "sel", "sel_tipo"):
            st.session_state.pop(k, None)
        st.rerun()

st.markdown(f"""<div class="pcc-hero">{_logo}
  <div><h1>Portal de Inspecciones TGI_</h1>
  <p>PCC Integrity — Protección catódica · CIPS · PAP · DCVG</p></div>
  <div class="pcc-badge">fits<br>you_</div></div>""", unsafe_allow_html=True)

st.session_state.setdefault("sel", None)
st.session_state.setdefault("sel_tipo", None)
st.session_state.setdefault("vista", "inspeccion")

# Navegación: por inspección individual o vista consolidada por tramo
if not st.session_state.sel:
    nv1, nv2, _ = st.columns([1.2, 1.4, 3])
    if nv1.button("📋 Por inspección",
                  type=("primary" if st.session_state.vista == "inspeccion" else "secondary")):
        st.session_state.vista = "inspeccion"
        st.rerun()
    if nv2.button("🔎 Vista por tramo",
                  type=("primary" if st.session_state.vista == "tramo" else "secondary")):
        st.session_state.vista = "tramo"
        st.rerun()

if st.session_state.sel:
    try:
        _tipo = st.session_state.sel_tipo or "CIPS"
        _det = cargar_detalle(st.session_state.sel, _tipo)
        if _tipo == "PAP":
            render_dashboard_pap(_det)
        elif _tipo == "DCVG":
            render_dashboard_dcvg(_det)
        else:
            render_dashboard_cips(_det)
    except Exception as e:
        st.error(f"No se pudo cargar la inspección: {e}")
        if st.button("← Volver"):
            st.session_state.sel = None
            st.session_state.sel_tipo = None
            st.rerun()
elif st.session_state.vista == "tramo":
    render_vista_tramo()
else:
    render_listado()

st.markdown("""<hr style="border:none;border-top:1px solid #DDDDDD;margin:2.2rem 0 .5rem;">
<div style="display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;
  color:#666;font-size:0.8rem;">
  <span><i>For Internal Use Only — Not For External Distribution. Property of PCC Integrity.</i></span>
  <b style="color:#C7113A;">www.pccintegrity.com</b></div>""", unsafe_allow_html=True)
