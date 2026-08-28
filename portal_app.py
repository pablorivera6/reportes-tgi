"""
Portal TGI — visualización de inspecciones de protección catódica (PCC Integrity).

App SEPARADA de la de procesamiento: solo LEE lo que PCC publica en Supabase y lo
muestra con un tablero anclado al contenido del informe. Diseño PCC.

La APARIENCIA vive en `portal_theme.py` (tokens, CSS, plantilla de gráficas y
componentes: barra_titulo / ficha / veredicto / kpi_row / chip / seccion). Aquí
solo va la lógica. Si tocas colores, tipografía o tarjetas, es allá.

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
import portal_theme as tema
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
                   layout="wide",
                   # en pantalla chica el cromo lateral se pliega solo
                   initial_sidebar_state="auto")

tema.aplicar(st)

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
    st.markdown(f"""<div style="max-width:430px;margin:4.5rem auto 1.2rem;
        text-align:center;">
      <div style="background:{tema.GRAFITO};border-radius:14px;padding:1.5rem;
        display:inline-block;margin-bottom:1.1rem;">{_logo}</div>
      <h1 style="font-size:1.5rem;font-weight:800;color:{tema.TINTA};margin:0;">
        Portal de Inspecciones TGI</h1>
      <p style="color:{tema.TINTA_3};font-size:.86rem;margin:.35rem 0 0;">
        PCC Integrity · Protección catódica</p></div>""",
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

# rol activo: 'revisor' (ingeniero PCC, ve y aprueba) o 'tgi' (cliente, solo
# aprobadas). En modo local el selector se dibuja dentro del cromo lateral.
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


# Los nulos NO se muestran como el texto "None" al cliente.
_GUION = "\u2014"


def _txt(v, guion=_GUION):
    if v is None:
        return guion
    if isinstance(v, float) and math.isnan(v):
        return guion
    t = str(v).strip()
    return t if t and t.lower() not in ("none", "nan", "nat") else guion


_NUMERICAS = ("ON [mV]", "OFF [mV]", "VAC [mV]", "Latitud", "Longitud",
              "Longitud [m]", "Longitud\u00b0", "Profundidad [m]", "Profundidad",
              "OL/RE [mV]", "P/RE [mV]", "Severidad %IR",
              "1 m [\u03a9\u00b7m]", "2 m [\u03a9\u00b7m]", "3 m [\u03a9\u00b7m]")


def _tabla_limpia(df, ocultar_vacias=True):
    """Columnas numericas como numero (el nulo queda en blanco, no 'None'),
    texto sin None, y fuera las columnas que quedaron 100% vacias."""
    df = df.copy()
    for c in df.columns:
        if c in _NUMERICAS:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        else:
            df[c] = df[c].map(lambda v: "" if _txt(v) == _GUION else str(v))
    if ocultar_vacias:
        vacias = [c for c in df.columns
                  if (df[c].isna().all() if c in _NUMERICAS else (df[c] == "").all())]
        if vacias and len(vacias) < len(df.columns):
            df = df.drop(columns=vacias)
    return df


def _pct_cumple(res, dfp):
    pct = res.get("pct_cumple")
    if pct is None and not dfp.empty:
        cd = dfp["off"].dropna()
        pct = round(100 * (cd <= -850).sum() / len(cd), 1) if len(cd) else 0.0
    return pct


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
    if insp.get("nota_revision"):
        st.caption(f"Nota de revisión: {insp['nota_revision']}")
    if not _ES_REVISOR or _DEMO:
        return
    if estado == "en_revision":
        st.info("Revisa el tablero y el informe descargable. Al **aprobar**, "
                "el cliente TGI podrá verlo en el portal.", icon=":material/gavel:")
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
_ESTADO_CHIP = {"aprobada": ("Aprobada", "ok"),
                "en_revision": ("En revisión", "warn"),
                "rechazada": ("Rechazada", "mal")}


def _chip_estado(insp):
    txt, tono = _ESTADO_CHIP.get(insp.get("estado", "aprobada"),
                                 (insp.get("estado", ""), "neu"))
    return tema.chip(txt, tono, punto=True)


def _encabezado(insp, subtitulo=""):
    """Ruta + título + estado, y debajo la ficha del informe."""
    if st.button("← Volver al listado", key=f"volver_{insp.get('id')}"):
        st.session_state.sel = None
        st.session_state.sel_tipo = None
        st.rerun()
    tema.barra_titulo(
        st, _txt(insp.get("tramo"), "Inspección"), via="Inspecciones",
        sufijo=insp.get("tipo", ""), derecha=_chip_estado(insp))
    tema.ficha(st, [
        ("Gasoducto", _txt(insp.get("gasoducto"))),
        ("Fecha", _txt(insp.get("fecha"))),
        ("Inspector", _txt(insp.get("inspector"))),
        ("OT", _txt(insp.get("ot"))),
        ("Ciclo", _txt(insp.get("ciclo"))),
        ("Punto inicial", _abscisa_txt(insp.get("abscisa_ini"))),
        ("Punto final", _abscisa_txt(insp.get("abscisa_fin"))),
    ])
    _barra_revision(insp)


# ── Render del dashboard CIPS ────────────────────────────────────────────────
def render_dashboard_cips(detalle):
    insp = detalle["inspeccion"]
    dfp = _df_puntos(detalle["puntos"])
    res = insp.get("resumen") or {}

    _encabezado(insp)

    # Veredicto: la pregunta del cliente es si el tramo cumple, y dónde no.
    total = res.get("total", len(dfp))
    pct = _pct_cumple(res, dfp)
    long_km = (res.get("longitud_m") or 0) / 1000
    _n_hall = res.get("n_hallazgos", len(detalle["hallazgos"]))
    _n_sin = res.get("n_tramos_no_insp", len(detalle["tramos"]))
    _fuera = int((dfp["off"].dropna() > -850).sum()) if not dfp.empty else 0
    tema.seccion(st, "Veredicto de protección")
    tema.veredicto(
        st, "Cumplimiento del criterio", f"{pct:.1f}%" if pct is not None else "—",
        tema.tono_cumple(pct),
        "Potencial OFF ≤ −850 mV (NACE SP0169)",
        [("Lecturas", f"{total:,}".replace(",", "."), "en el tramo", ""),
         ("Fuera de criterio", f"{_fuera:,}".replace(",", "."), "puntos > −850 mV",
          "alerta" if _fuera else "bien"),
         ("Longitud", f"{long_km:.2f} km" if long_km else "—", "inspeccionada", ""),
         ("Hallazgos", _n_hall, "registrados en campo", "aviso" if _n_hall else "bien"),
         ("Sin inspeccionar", _n_sin, "tramos" if _n_sin else "cobertura completa",
          "alerta" if _n_sin else "bien")])

    # Mapa + Gráfica de potenciales (VDC)
    tema.seccion(st, "Evidencia de campo")
    cmap, cvdc = st.columns([1, 1])
    with cmap:
        st.markdown("**Mapa — estado de protección**")
        mp = dfp.dropna(subset=["lat", "lon"])
        if not mp.empty:
            st.map(mp.rename(columns={"lat": "latitude", "lon": "longitude"}),
                   latitude="latitude", longitude="longitude", color="color", size=8)
            st.markdown(
                "".join(tema.chip(t, c, punto=True) + "&nbsp;"
                        for t, c in [("Protegido", "ok"), ("Desprotegido", "mal"),
                                     ("Sobreprotegido", "neu")]),
                unsafe_allow_html=True)
        else:
            st.info("Los puntos no tienen coordenadas.")
    with cvdc:
        st.markdown("**Potencial ON/OFF vs abscisa (Gráfica VDC)**")
        _grafica_vdc(dfp)

    # Gráfica VAC (solo si hay data VAC)
    if dfp["vac"].notna().any():
        st.write("")
        st.markdown("**Voltaje AC vs abscisa (Gráfica VAC)**")
        _grafica_vac(dfp)

    # ── Comparativa con histórico + rectificadores del tramo ─────────────────
    _hist = None
    _rects = []
    try:
        if db.disponible():
            _hist = db.historico_de_tramo(insp.get("tramo"), "CIPS")
            _rects = db.rectificadores_de_tramo(insp.get("tramo"))
    except Exception:
        pass
    if _hist and not dfp.empty:
        import comparativa
        tema.seccion(st, f"Comparativa con histórico · {_hist.get('periodo','')}")
        _r = comparativa.resumen_comparativo(dfp, _hist)
        _a, _h = _r["actual"], _r["historico"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Tramo protegido", f"{_a['pct_prot']}%",
                  delta=f"{(_a['pct_prot'] or 0) - (_h['pct_prot'] or 0):+.1f} pp"
                  if _a['pct_prot'] is not None and _h['pct_prot'] is not None else None)
        m2.metric("OFF promedio", f"{_a['prom_off']:.0f} mV" if _a['prom_off'] is not None else "—",
                  delta=f"{(_a['prom_off'] or 0) - (_h['prom_off'] or 0):+.0f} mV"
                  if _a['prom_off'] is not None and _h['prom_off'] is not None else None,
                  delta_color="inverse")
        m3.metric("Puntos fuera de criterio", _a['fuera'] if _a['fuera'] is not None else "—",
                  delta=(f"{(_a['fuera'] or 0) - (_h['fuera'] or 0):+d}"
                         if _a['fuera'] is not None and _h['fuera'] is not None else None),
                  delta_color="inverse")
        m4.metric("Puntos medidos", _a['n'], delta=f"{(_a['n'] or 0) - (_h['n'] or 0):+d}")
        st.plotly_chart(
            comparativa.overlay_plotly(dfp, _hist.get("puntos"), _hist.get("periodo", "histórico")),
            use_container_width=True)

    # Rectificadores asignados a este tramo
    if _rects:
        import rectificadores as rx
        tema.seccion(st, "Rectificadores del tramo")
        _k = rx.kpis(_rects)
        tema.kpi_row(st, [
            ("Rectificadores", _k["total"], tema.NEUTRO, "asignados al tramo"),
            ("Distritos", _k["distritos"], tema.NEUTRO, ""),
            ("En operación", _k["operando"], tema.VERDE, ""),
            ("Fuera de servicio", _k["fuera"],
             tema.ROJO if _k["fuera"] else tema.VERDE,
             "requieren atención" if _k["fuera"] else "ninguno")])
        for i, _rc in enumerate(_rects):
            rx.render_card(_rc, st, key=f"cips_{insp.get('id')}_{i}")

    # PDF del dashboard (con histórico y/o rectificadores)
    if (_hist or _rects) and not dfp.empty:
        import comparativa
        try:
            _pdf = comparativa.pdf_dashboard(detalle, dfp, _hist, rects=_rects)
            _nom = f"Dashboard_{(insp.get('tramo') or 'tramo').replace(' ', '_')}.pdf"
            st.download_button("⬇️ Descargar PDF del dashboard", data=_pdf,
                               file_name=_nom, mime="application/pdf")
        except Exception as e:
            st.caption(f"(No se pudo generar el PDF: {e})")

    # Tabla de potenciales
    tema.seccion(st, "Detalle de la inspección")
    st.markdown("**Potenciales CIPS**")
    tp = dfp.copy()
    tp["Abscisa"] = tp["abscisa"].apply(_abscisa_txt)
    tp = tp.rename(columns={"on": "ON [mV]", "off": "OFF [mV]", "estado": "Estado",
                            "vac": "VAC [mV]", "observaciones": "Observaciones",
                            "lat": "Latitud", "lon": "Longitud"})
    st.dataframe(_tabla_limpia(tp[["Abscisa", "ON [mV]", "OFF [mV]", "Estado",
                                   "VAC [mV]", "Latitud", "Longitud",
                                   "Observaciones"]]),
                 use_container_width=True, height=280, hide_index=True)

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
        st.dataframe(_tabla_limpia(dh), use_container_width=True, height=220,
                     hide_index=True)
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
        st.dataframe(_tabla_limpia(dt), use_container_width=True,
                     height=(38 * (len(dt) + 1) + 4), hide_index=True)
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
                      name="ON", line=dict(color=tema.TINTA_2, width=1)))
        fig.add_trace(go.Scatter(x=d["abscisa"], y=d["off"], mode="lines",
                      name="OFF (Instant)", line=dict(color=tema.MARCA, width=1.5)))
        fig.add_hline(y=-850, line=dict(color=tema.VERDE, dash="dash"),
                      annotation_text="−850 mV")
        fig.add_hline(y=-1200, line=dict(color=tema.AMBAR, dash="dash"),
                      annotation_text="−1200 mV")
        fig.update_layout(height=340, margin=dict(t=10, b=10, l=10, r=10),
                          xaxis_title="Abscisa [m]", yaxis_title="mV")
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
                      name="VAC", line=dict(color=tema.AZUL, width=1.3)))
        fig.add_hline(y=15, line=dict(color=tema.MARCA, dash="dash"),
                      annotation_text="15 VAC (SP0177)")
        fig.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10),
                          xaxis_title="Abscisa [m]", yaxis_title="V AC")
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
    pct = _pct_cumple(res, dfp)
    long_km = (res.get("longitud_m") or 0) / 1000
    _n_hall = res.get("n_hallazgos", len(detalle["hallazgos"]))
    _fuera = int((dfp["off"].dropna() > -850).sum()) if not dfp.empty else 0
    tema.seccion(st, "Veredicto de protección")
    tema.veredicto(
        st, "Cumplimiento del criterio", f"{pct:.1f}%" if pct is not None else "—",
        tema.tono_cumple(pct), "Potencial OFF ≤ −850 mV (NACE SP0169)",
        [("Postes medidos", f"{total:,}".replace(",", "."), "en el tramo", ""),
         ("Fuera de criterio", f"{_fuera:,}".replace(",", "."), "postes > −850 mV",
          "alerta" if _fuera else "bien"),
         ("Longitud", f"{long_km:.2f} km" if long_km else "—", "inspeccionada", ""),
         ("Hallazgos", _n_hall, "registrados en campo",
          "aviso" if _n_hall else "bien")])

    tema.seccion(st, "Evidencia de campo")
    cmap, cpot = st.columns([1, 1])
    with cmap:
        st.markdown("**Mapa — estado de protección**")
        mp = dfp.dropna(subset=["lat", "lon"])
        if not mp.empty:
            st.map(mp.rename(columns={"lat": "latitude", "lon": "longitude"}),
                   latitude="latitude", longitude="longitude", color="color", size=8)
            st.markdown(
                "".join(tema.chip(t, c, punto=True) + "&nbsp;"
                        for t, c in [("Protegido", "ok"), ("Desprotegido", "mal"),
                                     ("Sobreprotegido", "neu")]),
                unsafe_allow_html=True)
        else:
            st.info("Los postes no tienen coordenadas.")
    with cpot:
        st.markdown("**Potencial ON/OFF por poste vs abscisa**")
        _grafica_potenciales_pap(dfp)

    tema.seccion(st, "Detalle de la inspección")
    st.markdown("**Potenciales PAP**")
    tp = dfp.copy()
    tp["Abscisa"] = tp["abscisa"].apply(_abscisa_txt)
    tp = tp.rename(columns={"on": "ON [mV]", "off": "OFF [mV]", "estado": "Estado",
                            "observaciones": "Observaciones", "lat": "Latitud",
                            "lon": "Longitud"})
    st.dataframe(_tabla_limpia(tp[["Abscisa", "ON [mV]", "OFF [mV]", "Estado",
                                   "Latitud", "Longitud", "Observaciones"]]),
                 use_container_width=True, height=300, hide_index=True)

    st.markdown("**Hallazgos**")
    _tabla_hallazgos(detalle["hallazgos"])
    _descarga_informe(insp)


def _grafica_potenciales_pap(dfp):
    try:
        import plotly.graph_objects as go
        d = dfp.dropna(subset=["abscisa", "off"]).sort_values("abscisa")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=d["abscisa"], y=d["on"], mode="lines+markers",
                      name="ON", line=dict(color=tema.TINTA_2, width=1),
                      marker=dict(size=5)))
        fig.add_trace(go.Scatter(x=d["abscisa"], y=d["off"], mode="lines+markers",
                      name="OFF", line=dict(color=tema.MARCA, width=1.5),
                      marker=dict(size=5)))
        fig.add_hline(y=-850, line=dict(color=tema.VERDE, dash="dash"),
                      annotation_text="−850 mV")
        fig.add_hline(y=-1200, line=dict(color=tema.AMBAR, dash="dash"),
                      annotation_text="−1200 mV")
        fig.update_layout(height=340, margin=dict(t=10, b=10, l=10, r=10),
                          xaxis_title="Abscisa [m]", yaxis_title="mV")
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.caption(f"(gráfica no disponible: {e})")


# ── Render del dashboard DCVG (defectos + resistividad) ──────────────────────
COLOR_CLAS = tema.SEVERIDAD


def render_dashboard_dcvg(detalle):
    insp = detalle["inspeccion"]
    res = insp.get("resumen") or {}
    _encabezado(insp)

    dfd = pd.DataFrame(detalle["defectos"])
    conteo = res.get("por_clasificacion") or {}
    _n_def = res.get("n_defectos", len(dfd))
    _n_crit = res.get("n_criticos",
                      (conteo.get("Mediano", 0) + conteo.get("Grande", 0)))
    _n_hall = res.get("n_hallazgos", len(detalle["hallazgos"]))
    _tono_d = tema.ROJO if _n_crit else (tema.AMBAR if _n_def else tema.VERDE)
    tema.seccion(st, "Veredicto del recubrimiento")
    tema.veredicto(
        st, "Defectos críticos", _n_crit, _tono_d,
        "Severidad %IR Mediano o Grande — requieren intervención",
        [("Defectos totales", _n_def, "detectados", ""),
         ("Postes", res.get("n_postes", len(detalle["postes"])), "medidos", ""),
         ("Resistividades", res.get("n_resist", len(detalle["resistividades"])),
          "sondeos Wenner", ""),
         ("Hallazgos", _n_hall, "registrados en campo",
          "aviso" if _n_hall else "bien")])

    # distribución por clasificación (severidad del informe)
    if conteo:
        _cel = "".join(
            f"<div class='kpi' style='--tono:{COLOR_CLAS[c]}'>"
            f"<p class='kpi-lbl'>{c}</p>"
            f"<p class='kpi-val' style='color:{COLOR_CLAS[c] if conteo.get(c) else tema.TINTA_3}'>"
            f"{conteo.get(c, 0)}</p>"
            f"<p class='kpi-sub'>{'defectos' if conteo.get(c) != 1 else 'defecto'}</p></div>"
            for c in ["Muy Pequeño", "Pequeño", "Mediano", "Grande"])
        tema.seccion(st, "Distribución por severidad")
        st.markdown(f"<div class='kpi-row'>{_cel}</div>", unsafe_allow_html=True)

    tema.seccion(st, "Evidencia de campo")
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

    # ── Comparativa con la inspección DCVG anterior ──────────────────────────
    _hist = None
    try:
        if db.disponible():
            _hist = db.historico_de_tramo(insp.get("tramo"), "DCVG")
    except Exception:
        pass
    if _hist:
        import comparativa
        tema.seccion(st, f"Comparativa con histórico · {_hist.get('periodo','')}")
        _r = comparativa.resumen_comparativo_dcvg(dfd, _hist, res.get("longitud_m"))
        _a, _h = _r["actual"], _r["historico"]

        def _delta(clave, fmt="{:+d}"):
            va, vh = _a.get(clave), _h.get(clave)
            if isinstance(va, (int, float)) and isinstance(vh, (int, float)):
                return fmt.format(va - vh)
            return None

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Defectos", _a["n_defectos"], delta=_delta("n_defectos"),
                  delta_color="inverse")
        m2.metric("Defectos críticos", _a["n_criticos"], delta=_delta("n_criticos"),
                  delta_color="inverse")
        m3.metric("Densidad",
                  f"{_a['densidad_km']:.2f} def/km" if _a["densidad_km"] is not None else "—",
                  delta=_delta("densidad_km", "{:+.2f} def/km"), delta_color="inverse")
        m4.metric("Severidad máx.",
                  f"{_a['max_severidad']:.1f} %" if _a["max_severidad"] is not None else "—",
                  delta=_delta("max_severidad", "{:+.1f} pp"), delta_color="inverse")
        st.plotly_chart(
            comparativa.overlay_dcvg_plotly(dfd, _hist, _hist.get("periodo", "histórico")),
            use_container_width=True)
        st.caption(
            f"Histórico: {_h.get('n_defectos', 0)} defectos · "
            + " · ".join(f"{k} {v}" for k, v in
                         (_h.get("por_clasificacion") or {}).items())
            + f" · fuente: {_hist.get('fuente') or '—'}. "
            "Dos campañas DCVG no encuentran el defecto en la misma abscisa: "
            "lo comparable es cuántos hay, de qué severidad y cada cuánto.")

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
        st.dataframe(_tabla_limpia(td[[c for c in cols if c in td.columns]]),
                     use_container_width=True, height=300, hide_index=True)
    else:
        st.caption("Sin defectos registrados.")

    # tabla de resistividades
    if detalle["resistividades"]:
        st.markdown("**Resistividades (Wenner 1/2/3 m)**")
        tr = pd.DataFrame(detalle["resistividades"])
        tr["Abscisa"] = tr["abscisa"].apply(_abscisa_txt)
        tr = tr.rename(columns={"r1": "1 m [Ω·m]", "r2": "2 m [Ω·m]",
                                "r3": "3 m [Ω·m]", "sector": "Sector"})
        st.dataframe(_tabla_limpia(tr[[c for c in ["Abscisa", "Sector",
                         "1 m [Ω·m]", "2 m [Ω·m]", "3 m [Ω·m]"]
                         if c in tr.columns]]),
                     use_container_width=True, height=200, hide_index=True)

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
        for y, txt, col in [(15, "15%", tema.SEVERIDAD["Pequeño"]),
                            (35, "35%", tema.AMBAR), (60, "60%", tema.ROJO)]:
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
        for col, nombre, color in [("r1", "1 m", tema.TINTA_2),
                                   ("r2", "2 m", tema.AZUL),
                                   ("r3", "3 m", tema.MARCA)]:
            if col in d.columns and d[col].notna().any():
                fig.add_trace(go.Scatter(x=d["abscisa"], y=d[col], mode="lines+markers",
                              name=nombre, line=dict(color=color, width=1.2),
                              marker=dict(size=5)))
        fig.update_layout(height=280, margin=dict(t=10, b=10, l=10, r=10),
                          xaxis_title="Abscisa [m]", yaxis_title="Resistividad [Ω·m]")
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
        st.dataframe(_tabla_limpia(dh), use_container_width=True, height=200,
                     hide_index=True)
    else:
        st.caption("Sin hallazgos registrados.")


def _descarga_informe(insp):
    if not _DEMO and insp.get("excel_path"):
        url = db.url_descarga(insp["excel_path"], write=_ES_REVISOR)
        if url:
            st.link_button("⬇️ Descargar informe (Excel)", url)


# ── Listado de inspecciones ──────────────────────────────────────────────────
def render_listado():
    tema.barra_titulo(st, "Inspecciones publicadas",
                      via="Portal TGI <b>/</b> Inspecciones")
    try:
        lista = cargar_lista()
    except Exception as e:
        st.error(f"No se pudo leer el histórico: {e}")
        return
    if not lista:
        st.info("Aún no hay inspecciones publicadas.", icon=":material/inbox:")
        return

    # filtros por tipo y tramo
    st.write("")
    cf1, cf2, _sp = st.columns([1, 1, 1.4])
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
        fe = st.radio("Estado", ["Todas", "En revisión", "Aprobadas",
                                 "Rechazadas"], horizontal=True, index=0)
        mapa_e = {"En revisión": "en_revision", "Aprobadas": "aprobada",
                  "Rechazadas": "rechazada"}
        if fe in mapa_e:
            lista = [i for i in lista if i.get("estado") == mapa_e[fe]]
        pend = sum(1 for i in cargar_lista() if i.get("estado") == "en_revision")
        if pend:
            st.warning(f"{pend} inspección(es) esperando tu aprobación.",
                       icon=":material/pending_actions:")

    st.caption(f"{len(lista)} inspección(es)")
    for insp in lista:
        res = insp.get("resumen") or {}
        tipo = insp.get("tipo", "CIPS")
        veredicto, extra = _chips_listado(tipo, res)
        est = insp.get("estado", "aprobada")
        est_chip = _chip_estado(insp) if _ES_REVISOR else ""
        c1, c2 = st.columns([6, 1.15], vertical_alignment="center")
        with c1:
            st.markdown(f"""<div class="fila">
              <p class="fila-t">{tema.chip(tipo, 'tipo')}
                 <b>{_txt(insp.get('tramo'))}</b>
                 <span class="sep">|</span>
                 <span class="gas">{_txt(insp.get('gasoducto'), '')}</span>
                 {veredicto} {est_chip}</p>
              <p class="fila-m">
                 <span>Fecha <b>{_txt(insp.get('fecha'))}</b></span>
                 <span>Inspector <b>{_txt(insp.get('inspector'))}</b></span>
                 <span>OT <b>{_txt(insp.get('ot'))}</b></span>
                 <span>{extra}</span></p>
            </div>""", unsafe_allow_html=True)
        with c2:
            _rev = _ES_REVISOR and est == "en_revision"
            if st.button("Revisar" if _rev else "Abrir", key=f"ver-{insp['id']}",
                         type="primary" if _rev else "secondary",
                         use_container_width=True):
                st.session_state.sel = insp["id"]
                st.session_state.sel_tipo = tipo
                st.rerun()
        st.write("")


def _chips_listado(tipo, res):
    """(chip de veredicto, texto de volumen) según el tipo de inspección."""
    if tipo == "DCVG":
        crit = res.get("n_criticos", 0)
        extra = f"{_txt(res.get('n_defectos'), '?')} defectos"
        chip = (tema.chip(f"{crit} críticos", "mal", punto=True) if crit
                else tema.chip("Sin críticos", "ok", punto=True))
        return chip, extra
    # CIPS / PAP: cumplimiento -850
    pct = res.get("pct_cumple")
    extra = f"{_txt(res.get('total'), '?')} lecturas"
    if pct is None:
        return "", extra
    tono = "ok" if pct >= 95 else ("warn" if pct >= 85 else "mal")
    return tema.chip(f"Cumple {pct:.0f}%", tono, punto=True), extra


# ── Vista consolidada por tramo (CIPS + PAP + DCVG juntos) ───────────────────
def _off_de_punto(p):
    o = p.get("off_limpio") if p.get("off_limpio") is not None else p.get("off_mv")
    return o if o is not None else p.get("off")


def render_vista_tramo():
    tema.barra_titulo(st, "Vista consolidada por tramo",
                      via="Portal TGI <b>/</b> Por tramo")
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
    tema.seccion(st, "Inspecciones del tramo")
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

    tema.seccion(st, "Estado por técnica")
    _tarjetas = []
    for tp in ["CIPS", "PAP", "DCVG"]:
        if tp not in elegidas:
            _tarjetas.append((tp, "—", tema.TINTA_3, "sin inspección publicada"))
            continue
        r = elegidas[tp].get("resumen") or {}
        if tp == "DCVG":
            crit = r.get("n_criticos", 0)
            _tarjetas.append(("DCVG · defectos críticos", crit,
                              tema.ROJO if crit else tema.VERDE,
                              "Mediano + Grande" if crit else "ninguno crítico"))
        else:
            pct = r.get("pct_cumple")
            _tarjetas.append((f"{tp} · cumple ≤ −850 mV",
                              f"{pct:.0f}%" if pct is not None else "—",
                              tema.tono_cumple(pct),
                              "del tramo protegido" if pct is not None else ""))
    tema.kpi_row(st, _tarjetas)

    # gráfica alineada por abscisa (potencial arriba, severidad DCVG abajo)
    tema.seccion(st, "Protección vs defectos — alineado por abscisa")
    if not ({"CIPS", "PAP"} & set(det)):
        st.info("Este tramo aún no tiene CIPS ni PAP publicados: sin ellos no hay "
                "curva de protección con la cual cruzar los defectos.",
                icon=":material/info:")
    _grafica_consolidada(det)

    # mapa combinado
    tema.seccion(st, "Mapa combinado")
    _mapa_consolidado(det)

    # zonas críticas: desprotegido + defecto DCVG cercano
    tema.seccion(st, "Zonas críticas · ducto desprotegido con defecto de recubrimiento")
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
                              name="CIPS OFF", line=dict(color=tema.MARCA, width=1.3)),
                              row=1, col=1)
        # PAP (marcadores)
        if "PAP" in det:
            d = pd.DataFrame(det["PAP"]["puntos"])
            if not d.empty:
                d["off"] = d.apply(_off_de_punto, axis=1)
                d = d.dropna(subset=["abscisa", "off"]).sort_values("abscisa")
                fig.add_trace(go.Scatter(x=d["abscisa"], y=d["off"], mode="markers",
                              name="PAP OFF", marker=dict(color=tema.AZUL, size=6)),
                              row=1, col=1)
        fig.add_hline(y=-850, line=dict(color=tema.VERDE, dash="dash"), row=1, col=1)
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
                for y, col in [(15, tema.SEVERIDAD["Pequeño"]), (35, tema.AMBAR),
                               (60, tema.ROJO)]:
                    fig.add_hline(y=y, line=dict(color=col, dash="dash"), row=2, col=1)
                fig.update_yaxes(title_text="%IR", row=2, col=1)
            fig.update_xaxes(title_text="Abscisa [m]", row=2, col=1)
        else:
            fig.update_xaxes(title_text="Abscisa [m]", row=1, col=1)
        fig.update_layout(height=520 if tiene_dcvg else 340, showlegend=True,
                          margin=dict(t=40, b=10, l=10, r=10))
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
    st.dataframe(_tabla_limpia(dfz.sort_values("Prioridad")),
                 use_container_width=True, height=240, hide_index=True)


# ── Sección global de rectificadores (matriz) ───────────────────────────────
def render_rectificadores():
    import rectificadores as rx
    tema.barra_titulo(st, "Rectificadores", via="Portal TGI <b>/</b> Matriz")
    st.caption("Matriz de rectificadores inspeccionados: estado de operación, "
               "utilización y necesidades de mantenimiento. Cada unidad tiene su "
               "PDF descargable. Asigna un tramo para que aparezcan en su dashboard.")
    if _DEMO:
        st.info("Modo demostración: conecta Supabase para ver los rectificadores "
                "cargados.")
        return
    try:
        filas = db.listar_rectificadores(write=_ES_REVISOR)
    except Exception as e:
        if "rectificadores" in str(e) and "schema cache" in str(e):
            st.warning("La tabla de rectificadores aún no existe en Supabase. "
                       "Ejecuta `portal/schema_v7.sql` en el SQL Editor y luego "
                       "carga los datos con `cargar_rectificadores.py`.", icon="🛠️")
        else:
            st.error(f"No se pudieron leer los rectificadores: {e}")
        return
    if not filas:
        st.info("Aún no hay rectificadores cargados. Súbelos desde la app de "
                "procesamiento (o el script de carga).")
        return

    todos = [f.get("payload") for f in filas if f.get("payload")]
    k = rx.kpis(todos)
    tema.kpi_row(st, [
        ("Total", k["total"], tema.NEUTRO, "unidades en la matriz"),
        ("Distritos", k["distritos"], tema.NEUTRO, ""),
        ("En operación", k["operando"], tema.VERDE, ""),
        ("Fuera de servicio", k["fuera"],
         tema.ROJO if k["fuera"] else tema.VERDE,
         "requieren atención" if k["fuera"] else "ninguno")])

    # Asignación de tramo (solo revisor PCC)
    if _ES_REVISOR:
        with st.expander("🔧 Asignar tramo a cada rectificador (revisor PCC)"):
            edit = pd.DataFrame([{
                "id": f["id"], "TAG": f.get("tag") or "", "Estructura": f.get("estructura") or "",
                "Distrito": f.get("distrito") or "", "Tramo": f.get("tramo") or "",
            } for f in filas])
            ed = st.data_editor(
                edit, hide_index=True, use_container_width=True, key="rect_asign",
                column_config={"id": None,
                               "TAG": st.column_config.TextColumn(disabled=True),
                               "Estructura": st.column_config.TextColumn(disabled=True),
                               "Distrito": st.column_config.TextColumn(disabled=True),
                               "Tramo": st.column_config.TextColumn(
                                   help="Escribe el tramo del portal (p. ej. La Dorada)")})
            if st.button("💾 Guardar asignaciones"):
                prev = {f["id"]: (f.get("tramo") or "") for f in filas}
                n = 0
                for _, row in ed.iterrows():
                    nuevo = (row["Tramo"] or "").strip()
                    if nuevo != prev.get(row["id"], ""):
                        db.asignar_tramo_rectificador(row["id"], nuevo or None)
                        n += 1
                st.success(f"{n} asignación(es) actualizada(s)." if n else
                           "No hubo cambios.")
                st.rerun()

    # Filtros
    distritos = sorted({f.get("distrito") or "—" for f in filas})
    fabs = sorted({f.get("fabricante") for f in filas if f.get("fabricante")})
    cf1, cf2, cf3 = st.columns([1, 1, 1.4])
    fd = cf1.selectbox("Distrito", ["Todos"] + distritos)
    ff = cf2.selectbox("Fabricante", ["Todos"] + fabs)
    fq = cf3.text_input("🔍 Buscar TAG / modelo / serial").strip().lower()

    def _visible(f):
        if fd != "Todos" and (f.get("distrito") or "—") != fd:
            return False
        if ff != "Todos" and f.get("fabricante") != ff:
            return False
        if fq:
            blob = " ".join(str(f.get(x) or "") for x in
                            ("tag", "estructura", "modelo", "serial", "fabricante")).lower()
            if fq not in blob:
                return False
        return True

    vis = [f for f in filas if _visible(f)]
    if not vis:
        st.info("Ningún rectificador coincide con el filtro.")
        return

    # Agrupar por distrito
    por_distrito = {}
    for f in vis:
        por_distrito.setdefault(f.get("distrito") or "—", []).append(f)
    for distrito in sorted(por_distrito):
        grupo = por_distrito[distrito]
        tema.seccion(st, f"{distrito} · {len(grupo)} rectificador(es)")
        for f in grupo:
            rx.render_card(f["payload"], st, key=f["id"])


# ── App ──────────────────────────────────────────────────────────────────────
st.session_state.setdefault("sel", None)
st.session_state.setdefault("sel_tipo", None)
st.session_state.setdefault("vista", "inspeccion")

_VISTAS = [("inspeccion", "Inspecciones", ":material/description:"),
           ("tramo", "Vista por tramo", ":material/timeline:"),
           ("rectificadores", "Rectificadores", ":material/bolt:")]

with st.sidebar:
    st.markdown(f"<div class='sb-marca'>{_logo}<div><b>Portal TGI</b>"
                "<span>PCC Integrity</span></div></div>", unsafe_allow_html=True)
    st.markdown("<p class='sb-rot'>Navegación</p>", unsafe_allow_html=True)
    # La navegación vive aquí: se ve siempre, también dentro de una inspección.
    for _v, _lbl, _ic in _VISTAS:
        _activo = (st.session_state.vista == _v and not st.session_state.sel)
        if st.button(_lbl, key=f"nav_{_v}", icon=_ic,
                     type="primary" if _activo else "secondary"):
            st.session_state.vista = _v
            st.session_state.sel = None
            st.session_state.sel_tipo = None
            st.rerun()
    st.divider()
    st.markdown("<p class='sb-rot'>Estado</p>", unsafe_allow_html=True)
    if _DEMO:
        st.markdown(f"<div class='sb-pill'><i style='background:{tema.AMBAR}'></i>"
                    "Modo demostración · data de ejemplo</div>",
                    unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='sb-pill'><i style='background:{tema.VERDE}'></i>"
                    "Conectado al histórico</div>", unsafe_allow_html=True)
    st.markdown("<div class='sb-pill'><i style='background:%s'></i>%s</div>"
                % (tema.MARCA if _ES_REVISOR else "#7C8899",
                   "Revisor PCC · puedes aprobar" if _ES_REVISOR
                   else "Cliente TGI · solo lectura"), unsafe_allow_html=True)
    if not _PWD:
        _sel = st.radio("Ver como (modo local)", ["Cliente TGI", "Revisor PCC"],
                        key="rol_local", label_visibility="collapsed",
                        horizontal=False)
        _rol_nuevo = "revisor" if _sel == "Revisor PCC" else "tgi"
        if _rol_nuevo != st.session_state.get("rol"):
            st.session_state.rol = _rol_nuevo
            st.rerun()
        _ROL = _rol_nuevo
        _ES_REVISOR = (_ROL == "revisor")
    if st.session_state.get("portal_ok"):
        st.divider()
        if st.button("Salir", key="salir", icon=":material/logout:"):
            for k in ("portal_ok", "rol", "sel", "sel_tipo"):
                st.session_state.pop(k, None)
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
elif st.session_state.vista == "rectificadores":
    render_rectificadores()
else:
    render_listado()

tema.pie_pagina(st)
