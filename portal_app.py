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


_PWD = _pwd_portal()
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
                if hmac.compare_digest(clave, _PWD):
                    st.session_state.portal_ok = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta.")
    st.stop()


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
    return db.listar_inspecciones("CIPS")


def cargar_detalle(insp_id):
    if _DEMO:
        return _demo_detalle(insp_id)
    return db.cargar_inspeccion_cips(insp_id)


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


# ── Render del dashboard de UNA inspección ───────────────────────────────────
def render_dashboard(detalle):
    insp = detalle["inspeccion"]
    dfp = _df_puntos(detalle["puntos"])
    res = insp.get("resumen") or {}

    if st.button("← Volver al listado"):
        st.session_state.sel = None
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

    # filtro por tramo
    tramos = sorted({i.get("tramo") for i in lista if i.get("tramo")})
    f = st.selectbox("Filtrar por tramo", ["Todos"] + tramos, index=0)
    if f != "Todos":
        lista = [i for i in lista if i.get("tramo") == f]

    for insp in lista:
        res = insp.get("resumen") or {}
        pct = res.get("pct_cumple")
        chip = (f"<span class='chip chip-ok'>Cumple {pct:.0f}%</span>"
                if (pct is not None and pct >= 85)
                else f"<span class='chip chip-warn'>Cumple {pct:.0f}%</span>"
                if pct is not None else "")
        c1, c2 = st.columns([5, 1])
        with c1:
            st.markdown(f"""<div class="insp-card">
              <h4>{insp.get('tramo','—')} · {insp.get('gasoducto','')}</h4>
              <p class="insp-meta">📅 {insp.get('fecha','—')} &nbsp;·&nbsp;
                 👷 {insp.get('inspector','—')} &nbsp;·&nbsp; OT {insp.get('ot','—')}
                 &nbsp;·&nbsp; {res.get('total','?')} lecturas &nbsp; {chip}</p>
            </div>""", unsafe_allow_html=True)
        with c2:
            if st.button("Ver dashboard", key=f"ver-{insp['id']}"):
                st.session_state.sel = insp["id"]
                st.rerun()


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

st.markdown(f"""<div class="pcc-hero">{_logo}
  <div><h1>Portal de Inspecciones TGI_</h1>
  <p>PCC Integrity — Protección catódica · CIPS</p></div>
  <div class="pcc-badge">fits<br>you_</div></div>""", unsafe_allow_html=True)

st.session_state.setdefault("sel", None)
if st.session_state.sel:
    try:
        render_dashboard(cargar_detalle(st.session_state.sel))
    except Exception as e:
        st.error(f"No se pudo cargar la inspección: {e}")
        if st.button("← Volver"):
            st.session_state.sel = None
            st.rerun()
else:
    render_listado()

st.markdown("""<hr style="border:none;border-top:1px solid #DDDDDD;margin:2.2rem 0 .5rem;">
<div style="display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;
  color:#666;font-size:0.8rem;">
  <span><i>For Internal Use Only — Not For External Distribution. Property of PCC Integrity.</i></span>
  <b style="color:#C7113A;">www.pccintegrity.com</b></div>""", unsafe_allow_html=True)
