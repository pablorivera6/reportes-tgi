"""
PCC — Reportes TGI (versión web)
Interfaz Streamlit sobre el mismo motor de la app de escritorio:
readers / generator / conclusions / geo_utils / photo_utils / ppm_generator /
cips_lrs / cips_infra / cips_adapter se usan sin cambios.
"""
import os
import re
import base64
import tempfile
import datetime

import pandas as pd
import streamlit as st

from readers import FastFieldReader, EquipoReader, RectificadorReader, AislamientoReader
from geo_utils import KMZPipelineLoader, AbscisaCalculator
from generator import ReportGenerator, resource_path
from conclusions import ConclusionGenerator
from ppm_generator import PPMGenerator
from cips_infra import InfraTramos

def _b64_img(nombre):
    ruta = resource_path(nombre)
    if os.path.exists(ruta):
        with open(ruta, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


_LOGO_BLANCO = _b64_img("logo_white.png")   # para fondos rojo PCC
_LOGO_COLOR = _b64_img("logo.png")          # para fondos claros
_ICONO = resource_path("logo.png")

st.set_page_config(page_title="PCC Integrity – Reportes TGI",
                   page_icon=_ICONO if os.path.exists(_ICONO) else "⚡",
                   layout="wide", initial_sidebar_state="expanded")

# ── Design system PCC Integrity ──────────────────────────────────────────────
# Paleta exacta de marca: Rojo PCC C7113A · gris 333333 / 666666 / F5F5F5 /
# DDDDDD. Tipografía Calibri. Títulos en rojo terminados en "_".
st.markdown("""
<style>
  html, body, .stApp, .stApp * { font-family: Calibri, 'Segoe UI',
    -apple-system, 'Helvetica Neue', sans-serif; }
  /* Restaurar la fuente de íconos (el override anterior la pisa y los
     ligature-icons como "upload" se ven como texto encima del botón). */
  .stApp [data-testid="stIconMaterial"], .stApp .material-symbols-rounded,
  .stApp .material-symbols-outlined, .stApp .material-icons {
    font-family: 'Material Symbols Rounded', 'Material Symbols Outlined',
      'Material Icons' !important;
  }
  .stApp { background: #FFFFFF; }
  h2, h3 { color: #C7113A !important; font-weight: 700 !important; }

  [data-testid="stSidebar"] > div:first-child { background: #C7113A !important; }
  [data-testid="stSidebar"] * { color: #FFFFFF !important; }
  [data-testid="stSidebar"] hr { border-color: rgba(255,255,255,0.35) !important; }

  .stButton > button {
    background: #C7113A !important; color: #FFFFFF !important;
    border: none !important; border-radius: 6px !important;
    font-weight: 700 !important;
  }
  .stButton > button:hover { background: #A50E30 !important; }
  .stButton > button:disabled { background: #DDDDDD !important; color: #666666 !important; }

  [data-testid="stDownloadButton"] > button {
    background: #FFFFFF !important; color: #C7113A !important;
    border: 1.5px solid #C7113A !important; border-radius: 6px !important;
    font-weight: 700 !important;
  }
  [data-testid="stDownloadButton"] > button:hover { background: #F5F5F5 !important; }

  .stTabs [data-baseweb="tab-list"] {
    gap: 0.15rem; border-bottom: 1px solid #DDDDDD;
  }
  .stTabs [data-baseweb="tab"] { color: #666666; font-weight: 600; }
  .stTabs [aria-selected="true"] { color: #C7113A !important; font-weight: 700; }

  [data-testid="stMetricValue"] { color: #C7113A; }
  .pcc-hero { background: #C7113A; color: #FFFFFF; border-radius: 8px;
    padding: 1.1rem 1.6rem; margin-bottom: 1rem;
    display: flex; align-items: center; gap: 1.2rem; }
  .pcc-hero h1 { margin: 0; font-size: 1.55rem; font-weight: 800;
    color: #FFFFFF !important; }
  .pcc-hero p { margin: 0.15rem 0 0; opacity: 0.9; font-size: 0.9rem; }
  .pcc-badge { margin-left: auto; background: #FFFFFF; color: #C7113A;
    font-weight: 800; font-size: 0.8rem; line-height: 1.05;
    border-radius: 6px; padding: 0.45rem 0.6rem; text-align: center; }

  #MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Candado de acceso ────────────────────────────────────────────────────────
# La app corre pública en Streamlit Cloud; el acceso se restringe con una
# contraseña de equipo definida en Secrets ([app] password = "..."). Si el
# secret no existe (desarrollo local / tests), el candado queda desactivado.

def _password_equipo():
    try:
        return str(st.secrets.get("app", {}).get("password", ""))
    except Exception:
        return ""


_PWD_EQUIPO = _password_equipo()
if _PWD_EQUIPO and not st.session_state.get("auth_ok"):
    import hmac
    _logo_login = (f'<img src="data:image/png;base64,{_LOGO_BLANCO}" '
                   f'style="height:64px;" alt="PCC Integrity">' if _LOGO_BLANCO else '')
    st.markdown(f"""
    <div class="pcc-hero" style="max-width:520px;margin:3rem auto 1rem;">
      {_logo_login}
      <div><h1>Reportes TGI_</h1>
      <p>Acceso restringido al equipo PCC</p></div>
    </div>
    """, unsafe_allow_html=True)
    _, centro, _ = st.columns([1, 2, 1])
    with centro:
        with st.form("pcc_login"):
            clave = st.text_input("Contraseña de acceso", type="password")
            if st.form_submit_button("Entrar"):
                if hmac.compare_digest(clave, _PWD_EQUIPO):
                    st.session_state.auth_ok = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta.")
    st.stop()


# ── Estado ────────────────────────────────────────────────────────────────────

def init_state():
    if "data" not in st.session_state:
        st.session_state.data = {
            'info': {},
            'potenciales': [],
            'cips': [],
            'hallazgos': [],
            'rectificadores': [],
            'aislamientos': [],
            'inspecciones': {},
            'conclusiones': [],
            'recomendaciones': [],
            'firmas': {'elaboro': {}, 'reviso': {}, 'aprobo': {}},
        }
    st.session_state.setdefault("active_inspections", {
        'marco_h': False, 'ce': False, 'anodos': False,
        'cupones_ir': False, 'cupones_grav': False, 'pe': False})
    st.session_state.setdefault("equipos_inspector", [])
    st.session_state.setdefault("current_route_id", "")
    st.session_state.setdefault("informe_bytes", None)
    st.session_state.setdefault("ppm_bytes", None)
    st.session_state.setdefault("informe_nombre", "")


@st.cache_resource(show_spinner="Cargando KMZ de infraestructura...")
def cargar_kmz():
    ruta = resource_path("Infra_General_TGI_V11_29032023.kmz")
    if not os.path.exists(ruta):
        return None
    return KMZPipelineLoader(ruta)


@st.cache_resource
def cargar_infra_tramos():
    try:
        return InfraTramos()
    except Exception:
        return None


def get_abscisa_calculator(kmz, route_id=None):
    """Calculador para la ruta dada (o la primera disponible)."""
    if kmz is None:
        return None
    rid = route_id
    if rid:
        coords = kmz.get_pipeline_coords(rid)
        if not coords:
            resolved = kmz.find_route_by_name(rid)
            if resolved:
                rid = resolved
                coords = kmz.get_pipeline_coords(rid)
    else:
        rutas = kmz.get_all_route_ids()
        rid = rutas[0] if rutas else None
        coords = kmz.get_pipeline_coords(rid) if rid else []
    if not coords:
        return None
    return AbscisaCalculator(coords, kmz.get_pks_for_route(rid))


def _tmp_files(uploaded_files):
    """Guarda file_uploaders a disco temporal y devuelve las rutas."""
    rutas = []
    tmpdir = tempfile.mkdtemp(prefix="tgi_up_")
    for uf in uploaded_files:
        ruta = os.path.join(tmpdir, uf.name)
        with open(ruta, "wb") as f:
            f.write(uf.getbuffer())
        rutas.append(ruta)
    return rutas


# ── Autollenado (port de app.py de escritorio) ────────────────────────────────

def autofill_from_infrastructure(tramo_name):
    out = {}
    ruta = resource_path('Infraestrutura TGI.xlsx')
    if not os.path.exists(ruta):
        return out
    try:
        df = pd.read_excel(ruta, header=1)
        if 'GASODUCTO.1' in df.columns:
            df['GASODUCTO.1'] = df['GASODUCTO.1'].ffill()
        if 'TRAMOS' not in df.columns:
            return out
        df = df.dropna(subset=['TRAMOS'])
        matches = df[df['TRAMOS'].astype(str).str.contains(tramo_name, case=False, na=False)]
        if matches.empty:
            return out
        row = matches.iloc[0]
        exact = df[df['TRAMOS'].astype(str).str.lower() == tramo_name.lower()]
        if not exact.empty:
            row = exact.iloc[0]
        gas = None
        if 'GASODUCTO.1' in row and pd.notna(row['GASODUCTO.1']):
            gas = row['GASODUCTO.1']
        elif 'GASODUCTO' in row and pd.notna(row['GASODUCTO']):
            gas = row['GASODUCTO']
        if gas:
            out['gasoducto'] = str(gas)
        diam_cols = [c for c in df.columns if 'Di' in str(c) and 'metro' in str(c)]
        if not diam_cols:
            diam_cols = [c for c in df.columns if 'pulg' in str(c).lower()]
        if diam_cols and pd.notna(row[diam_cols[0]]):
            out['diametro'] = str(row[diam_cols[0]])
        if 'Recubrimiento' in row and pd.notna(row['Recubrimiento']):
            out['tipo_recubrimiento'] = str(row['Recubrimiento'])
        if 'Tipo' in row and pd.notna(row['Tipo']):
            out['tipo_ducto'] = str(row['Tipo'])
    except Exception as e:
        st.warning(f"Autollenado de infraestructura falló: {e}")
    return out


def autofill_ot_km(tramo_name):
    out = {}
    ruta = resource_path("consolidado OT.xlsx")
    if not os.path.exists(ruta):
        return out
    try:
        df = pd.read_excel(ruta)
        if 'SUBSISTEMA' not in df.columns:
            return out
        matches = df[df['SUBSISTEMA'].astype(str).str.contains(tramo_name, case=False, na=False)]
        if matches.empty:
            return out
        row = matches.iloc[0]
        if 'Orden' in df.columns and pd.notna(row['Orden']):
            try:
                out['ot'] = str(int(float(row['Orden'])))
            except Exception:
                out['ot'] = str(row['Orden']).strip()
        if 'Distrito' in df.columns and pd.notna(row['Distrito']):
            out['distrito'] = str(row['Distrito'])
        if 'Unidad [Km]' in df.columns and pd.notna(row['Unidad [Km]']):
            try:
                out['longitud_km'] = float(row['Unidad [Km]'])
            except Exception:
                pass
    except Exception as e:
        st.warning(f"Autollenado de OT falló: {e}")
    return out


def get_equipos_for_inspector(inspector_name):
    ruta = resource_path("Listado equipos TGI.xlsx")
    if not os.path.exists(ruta):
        return None, None, []
    try:
        df = pd.read_excel(ruta, header=2)
        inspector_name = inspector_name.strip().upper()
        if "LUIS BENITEZ" in inspector_name:
            inspector_name = "EVELIO ALVAREZ"
        serial, fecha_cal, equipos = "", "", []
        for _, row in df.iterrows():
            if pd.isna(row.iloc[1]):
                continue
            insp = str(row.iloc[1]).strip().upper()
            if insp == inspector_name or \
               len(set(insp.split()) & set(inspector_name.split())) >= 2:
                equipo = str(row.iloc[2]).strip()
                marca = str(row.iloc[3]).strip()
                ser = str(row.iloc[4]).strip()
                fc = row.iloc[5]
                if "DATALOG" in equipo.upper():
                    serial = ser
                    if pd.notna(fc):
                        fecha_cal = fc.strftime('%d/%m/%Y') if isinstance(fc, pd.Timestamp) \
                            else str(fc).split()[0]
                equipos.append(f"{equipo}: {marca} - {ser}")
        return serial, fecha_cal, equipos
    except Exception:
        return None, None, []


# ── App ───────────────────────────────────────────────────────────────────────

init_state()
data = st.session_state.data

# Aplicar autollenado pendiente ANTES de instanciar los widgets (los widgets con
# key conservan su estado; la única forma de actualizarlos es escribir su clave
# en session_state antes de crearlos en este run).
if st.session_state.get("pending_autofill"):
    for k, v in st.session_state.pending_autofill.items():
        st.session_state[f"info_{k}"] = str(v)
    st.session_state.pending_autofill = None

kmz = cargar_kmz()
infra_tramos = cargar_infra_tramos()

with st.sidebar:
    _logo_html = (f'<img src="data:image/png;base64,{_LOGO_BLANCO}" '
                  f'style="width:110px;margin-bottom:0.4rem;" alt="PCC Integrity">'
                  if _LOGO_BLANCO else
                  '<div style="font-size:1.25rem;font-weight:800;">PCC Integrity</div>')
    st.markdown(f"""
    <div style="padding:1rem 0 0.4rem;text-align:center;">
      {_logo_html}
      <div style="font-size:0.8rem;opacity:0.9;">Reportes TGI</div>
      <div style="font-size:0.75rem;font-weight:800;margin-top:0.2rem;">fits you_</div>
    </div><hr style="margin:0.4rem 0;">
    """, unsafe_allow_html=True)
    st.caption(f"KMZ: {'✅ cargado' if kmz else '❌ no encontrado'}")
    st.caption(f"Potenciales: {len(data['potenciales'])}")
    st.caption(f"CIPS: {len(data['cips'])} · Hallazgos: {len(data['hallazgos'])}")
    st.caption(f"Rectificadores: {len(data['rectificadores'])} · Aislam.: {len(data['aislamientos'])}")

_hero_logo = (f'<img src="data:image/png;base64,{_LOGO_BLANCO}" '
              f'style="height:52px;" alt="PCC Integrity">' if _LOGO_BLANCO else '')
st.markdown(f"""
<div class="pcc-hero">
  {_hero_logo}
  <div>
    <h1>Generador de Reportes TGI_</h1>
    <p>PCC Integrity — Inspecciones PAP / CIPS</p>
  </div>
  <div class="pcc-badge">fits<br>you_</div>
</div>
""", unsafe_allow_html=True)

tabs = st.tabs(["📝 Datos Generales", "📂 Cargar Archivos", "📊 Potenciales PAP",
                "📉 CIPS", "⚠️ Hallazgos", "🔌 Rectificadores", "🛠️ Insp. Especiales",
                "🔗 Aislamientos", "🖼️ Fotos IA", "📋 Conclusiones", "✍️ Firmas",
                "🚀 Generar"])

FIELD_LABELS = [('gasoducto', 'Gasoducto'), ('tramo', 'Tramo'),
                ('tipo_ducto', 'Tipo Ducto'), ('contrato', 'Contrato'),
                ('ot', 'OT'), ('contratista', 'Contratista'), ('fecha', 'Fecha'),
                ('inspector', 'Inspector'), ('serial_equipo', 'Serial Equipo'),
                ('fecha_calibracion', 'Fecha Calibración'), ('diametro', 'Diámetro'),
                ('tipo_recubrimiento', 'Tipo Recubrimiento'), ('ciclo', 'Ciclo')]

# ── Tab 1: Datos Generales ────────────────────────────────────────────────────
with tabs[0]:
    cols = st.columns(3)
    for i, (key, label) in enumerate(FIELD_LABELS):
        with cols[i % 3]:
            data['info'][key] = st.text_input(label, value=data['info'].get(key, ''),
                                              key=f"info_{key}")
    data['info']['tipo_inspeccion'] = st.selectbox(
        "Tipo Inspección", ["PAP", "CIPS", "DCVG"],
        index=["PAP", "CIPS", "DCVG"].index(data['info'].get('tipo_inspeccion', 'PAP')))
    if st.button("🔄 Autollenar desde el tramo"):
        tramo = re.sub(r'\s*\(?PK.*', '', data['info'].get('tramo', '')).strip()
        if tramo:
            cambios = autofill_from_infrastructure(tramo)
            extra = autofill_ot_km(tramo)
            if 'ot' in extra:
                cambios['ot'] = extra['ot']
            if 'distrito' in extra:
                data['info']['distrito'] = extra['distrito']
            if 'longitud_km' in extra:
                data['info']['longitud_km'] = extra['longitud_km']
            insp = data['info'].get('inspector', '')
            if insp:
                serial, fc, eqs = get_equipos_for_inspector(insp)
                if serial:
                    cambios['serial_equipo'] = serial
                if fc:
                    cambios['fecha_calibracion'] = fc
                if eqs:
                    st.session_state.equipos_inspector = eqs
                if not data['info'].get('contratista'):
                    cambios['contratista'] = 'PCC'
            data['info'].update(cambios)
            # Los text_input con key conservan su estado: los actualizamos vía
            # pending_autofill al inicio del próximo run.
            st.session_state.pending_autofill = cambios
            st.rerun()
        else:
            st.warning("Escribe primero el Tramo.")

# ── Tab 2: Cargar Archivos ────────────────────────────────────────────────────
with tabs[1]:
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("FASTFIELD — Potenciales_")
        ff = st.file_uploader("Excel FASTFIELD", type=["xlsx"],
                              accept_multiple_files=True, key="up_ff")
        if ff and st.button("Procesar FASTFIELD"):
            try:
                reader = FastFieldReader()
                nuevos = 0
                for ruta in _tmp_files(ff):
                    d = reader.read(ruta)
                    pots = d['potenciales']
                    tramos_unicos = sorted({p['tramo'] for p in pots if p.get('tramo')})
                    if len(tramos_unicos) > 1:
                        st.session_state.setdefault('ff_pendiente', []).append((d, tramos_unicos))
                        continue
                    data['potenciales'].extend(pots)
                    nuevos += len(pots)
                    for k_src, k_dst in [('tramo', 'tramo'), ('contrato', 'contrato'),
                                         ('tecnico', 'inspector'), ('fecha', 'fecha'),
                                         ('tipo_tramo', 'tipo_ducto')]:
                        if d.get(k_src):
                            data['info'][k_dst] = d[k_src]
                    if pots:
                        st.session_state.current_route_id = pots[0].get('route_id', '')
                # Post-proceso: marco H y tramos aéreos (igual que escritorio)
                data['inspecciones'].setdefault('marco_h', [])
                sorted_pots = sorted(data['potenciales'], key=lambda x: x.get('abscisa', 0))
                tramos_aereos, current = [], None
                for p in sorted_pots:
                    obs = str(p.get('observaciones', '')).lower()
                    ref = str(p.get('ref_geografica', '')).lower()
                    if 'marco h' in obs or 'marco h' in ref:
                        data['inspecciones']['marco_h'].append({
                            'route_id': p.get('route_id'), 'abscisado': p.get('abscisa_str'),
                            'fecha': p.get('fecha'), 'pot_on_gasoducto': None,
                            'pot_off_gasoducto': None, 'pot_on_marco': p.get('on_mv'),
                            'pot_off_marco': p.get('off_mv'),
                            'aislado': 1 if ('aislado' in obs or 'buen' in str(p.get('conexiones', '')).lower()) else 0,
                            'estado_aislante': 'Buen Estado', 'lat': p.get('lat'),
                            'lon': p.get('lon'), 'estado_pintura': p.get('pintura', 'Bueno'),
                            'observaciones': p.get('observaciones', '')})
                    if 'tierra aire' in obs or 'tierra aire' in ref:
                        current = {'route_id': p.get('route_id'),
                                   'inicio_abscisa_val': p.get('abscisa', 0),
                                   'inicio_abscisa': p.get('abscisa_str', ''),
                                   'lat_inicio': p.get('lat'), 'lon_inicio': p.get('lon'),
                                   'fecha': p.get('fecha')}
                    elif ('aire tierra' in obs or 'aire tierra' in ref) and current:
                        current.update({'fin_abscisa_val': p.get('abscisa', 0),
                                        'fin_abscisa': p.get('abscisa_str', ''),
                                        'lat_fin': p.get('lat'), 'lon_fin': p.get('lon')})
                        current['longitud'] = current['fin_abscisa_val'] - current['inicio_abscisa_val']
                        tramos_aereos.append(current)
                        current = None
                data['inspecciones']['tramos_aereos'] = tramos_aereos
                st.success(f"{nuevos} potenciales cargados.")
            except Exception as e:
                st.error(f"Error cargando FASTFIELD: {e}")
        if st.session_state.get('ff_pendiente'):
            d, tramos_unicos = st.session_state.ff_pendiente[0]
            sel = st.multiselect("El archivo tiene varios tramos; elige cuál(es) importar:",
                                 tramos_unicos, key="ff_sel")
            if st.button("Importar tramos elegidos"):
                pots = [p for p in d['potenciales'] if p.get('tramo') in sel]
                data['potenciales'].extend(pots)
                if sel:
                    data['info']['tramo'] = sel[0]
                st.session_state.ff_pendiente.pop(0)
                st.rerun()

        st.subheader("Equipos — Hallazgos DCP_")
        eq = st.file_uploader("Excel EQUIPOS", type=["xlsx"],
                              accept_multiple_files=True, key="up_eq")
        if eq and st.button("Procesar EQUIPOS"):
            try:
                reader = EquipoReader()
                calc = get_abscisa_calculator(kmz, st.session_state.current_route_id or None)
                for ruta in _tmp_files(eq):
                    d = reader.read(ruta)
                    data['hallazgos'].extend(d['hallazgos'])
                    info = d['survey_info']
                    route_id = kmz.find_route_by_name(info['pipeline']) if (kmz and info['pipeline']) else None
                    for h in d['hallazgos']:
                        h.setdefault('route_id', route_id)
                    if info['pipeline'] and not data['info'].get('gasoducto'):
                        data['info']['gasoducto'] = info['pipeline']
                    if info['cycle_on_ms'] and not data['info'].get('ciclo'):
                        data['info']['ciclo'] = f"{info['cycle_on_ms']}/{info['cycle_off_ms']} ms"
                for h in data['hallazgos']:
                    if h.get('abscisa') is None and h.get('lat') and h.get('lon') and calc:
                        m = calc.calculate(h['lat'], h['lon'])
                        h['abscisa'] = calc.format_abscisa(m)
                        h['abscisa_val'] = m
                    elif h.get('abscisa_val') is None:
                        m = AbscisaCalculator.parse_abscisa(str(h.get('abscisa', '0+000')))
                        h['abscisa_val'] = m
                data['hallazgos'].sort(key=lambda x: x.get('abscisa_val', 0))
                st.success(f"{len(data['hallazgos'])} hallazgos en total.")
            except Exception as e:
                st.error(f"Error cargando EQUIPOS: {e}")

    with c2:
        st.subheader("Data CIPS — Motor LRS_")
        if infra_tramos:
            emp = st.selectbox("Empresa", ["TGI", "OCENSA"], key="cips_emp")
            if emp == "TGI":
                dist = st.selectbox("Distrito", infra_tramos.distritos_tgi(), key="cips_dist")
                tramo_cips = st.selectbox("Tramo", infra_tramos.tramos("TGI", dist), key="cips_tr")
            else:
                dist = None
                tramo_cips = st.selectbox("Tramo", infra_tramos.tramos("OCENSA"), key="cips_tr_oc")
            cips_files = st.file_uploader("Excel CIPS", type=["xlsx"],
                                          accept_multiple_files=True, key="up_cips")
            if cips_files and st.button("Procesar CIPS"):
                shp = infra_tramos.shapefile(empresa=emp, tramo=tramo_cips, distrito=dist)
                if not shp:
                    st.error(f"No hay shapefile para el tramo '{tramo_cips}'.")
                else:
                    try:
                        with st.spinner("Procesando CIPS (LRS)..."):
                            from cips_lrs import procesar_cips_lrs
                            from cips_adapter import lrs_df_a_cips_dicts
                            df = procesar_cips_lrs(_tmp_files(cips_files), shp)
                            dicts = lrs_df_a_cips_dicts(df)
                            data['cips'] = dicts
                        st.success(f"{len(dicts)} registros CIPS procesados "
                                   f"({len(cips_files)} archivo(s); cada "
                                   f"procesamiento reemplaza la data anterior).")
                        if df.attrs.get("fuente_abscisa") == "EQUIPO":
                            st.info("El GPS de este archivo no varía entre "
                                    "lecturas, así que la abscisa se tomó del "
                                    "odómetro del equipo (Dist From Start), "
                                    "anclada a la etiqueta 'pk' del comentario "
                                    "si existe.")
                    except Exception as e:
                        from cips_lrs import TramoIncorrectoError
                        st.error(f"Error procesando CIPS: {e}")
                        if isinstance(e, TramoIncorrectoError) and e.lat:
                            sugs = infra_tramos.sugerir_tramos(e.lat, e.lon)
                            if sugs:
                                lineas = "\n".join(
                                    f"- **{t}** (Distrito {d}, {i})"
                                    for t, d, i in sugs[:5])
                                st.warning("Según las coordenadas del archivo, "
                                           "los datos parecen corresponder a:\n"
                                           + lineas)
        else:
            st.warning("No se encontró la base de infraestructura de tramos.")

        st.subheader("Rectificadores_")
        rec = st.file_uploader("Excel Rectificador (URPC)", type=["xlsx"],
                               accept_multiple_files=True, key="up_rec")
        if rec and st.button("Procesar Rectificadores"):
            try:
                reader = RectificadorReader()
                for ruta in _tmp_files(rec):
                    d = reader.read(ruta)
                    if d:
                        data['rectificadores'].append(d)
                st.success(f"{len(data['rectificadores'])} rectificadores cargados.")
            except Exception as e:
                st.error(f"Error cargando rectificadores: {e}")

        st.subheader("Aislamientos_")
        ais = st.file_uploader("Excel Aislamientos FastField", type=["xlsx"],
                               accept_multiple_files=True, key="up_ais")
        if ais and st.button("Procesar Aislamientos"):
            try:
                data['aislamientos'] = AislamientoReader().read_files(_tmp_files(ais))
                st.success(f"{len(data['aislamientos'])} aislamientos cargados.")
            except Exception as e:
                st.error(f"Error cargando aislamientos: {e}")

# ── Tabs 3-6, 8: tablas ───────────────────────────────────────────────────────
with tabs[2]:
    if data['potenciales']:
        st.dataframe(pd.DataFrame(data['potenciales'])[
            ['abscisa_str', 'fecha', 'ref_geografica', 'on_mv', 'off_mv', 'vac',
             'resistencia', 'ir_on_off', 'lat', 'lon', 'pintura', 'conexiones',
             'tipo_mant', 'observaciones']], use_container_width=True, height=420)
    else:
        st.info("Aún no hay potenciales. Carga archivos FASTFIELD.")

with tabs[3]:
    if data['cips']:
        st.dataframe(pd.DataFrame(data['cips'])[
            ['abscisa_val', 'on_mv', 'off_mv', 'on_limpio', 'off_limpio',
             'lat', 'lon', 'observaciones']], use_container_width=True, height=420)
    else:
        st.info("Aún no hay data CIPS.")

with tabs[4]:
    if data['hallazgos']:
        st.dataframe(pd.DataFrame(data['hallazgos'])[
            ['abscisa', 'tipo', 'descripcion', 'lat', 'lon', 'fecha']],
            use_container_width=True, height=420)
    else:
        st.info("Aún no hay hallazgos.")

with tabs[5]:
    if data['rectificadores']:
        filas = []
        for r in data['rectificadores']:
            ui = r.get('ultima_inspeccion', {})
            filas.append({'Nombre': r.get('nombre'), 'Gasoducto': r.get('gasoducto'),
                          'V Nominal': r.get('voltaje_nominal'),
                          'I Nominal': r.get('corriente_nominal'),
                          'V Oper': ui.get('vdc_salida'), 'I Oper': ui.get('idc_salida'),
                          'TAPS': ui.get('taps')})
        st.dataframe(pd.DataFrame(filas), use_container_width=True)
    else:
        st.info("Aún no hay rectificadores.")

with tabs[6]:
    st.write("Marca las inspecciones especiales realizadas:")
    for key, label in [('marco_h', 'Marco H'), ('ce', 'Cruces Encamisados'),
                       ('anodos', 'Ánodos'), ('cupones_ir', 'Cupones IR FREE'),
                       ('cupones_grav', 'Cupones Gravimétricos'), ('pe', 'Puentes Eléctricos')]:
        st.session_state.active_inspections[key] = st.checkbox(
            label, value=st.session_state.active_inspections[key], key=f"chk_{key}")

with tabs[7]:
    if data['aislamientos']:
        st.dataframe(pd.DataFrame(data['aislamientos'])[
            ['abscisado', 'tag', 'clase', 'diametro', 'tipo_brida',
             'pot_on_arriba', 'pot_off_arriba', 'diagnostico']],
            use_container_width=True, height=420)
    else:
        st.info("Aún no hay aislamientos.")

# ── Tab 9: Fotos IA ───────────────────────────────────────────────────────────
with tabs[8]:
    st.write("Sube las fotos de la inspección (JPG/PNG). Se ubican por GPS del EXIF "
             "y se clasifican con IA si hay llave de Gemini configurada.")
    fotos = st.file_uploader("Fotos", type=["jpg", "jpeg", "png"],
                             accept_multiple_files=True, key="up_fotos")
    if fotos and st.button("Procesar Fotos"):
        calc = get_abscisa_calculator(kmz, st.session_state.current_route_id or None)
        if not calc:
            st.error("No hay KMZ/ruta para calcular abscisas. Carga primero un FASTFIELD.")
        else:
            try:
                api_key = st.secrets.get("gemini", {}).get("api_key", "")
            except Exception:
                api_key = ""
            from photo_utils import PhotoProcessor
            proc = PhotoProcessor(api_key=api_key or None)
            rutas = _tmp_files(fotos)
            prog = st.progress(0)
            nuevos = 0
            KEYWORDS = ['via', 'vía', 'caño', 'tension', 'tensión', 'at', 'mt', 'bt',
                        'enmontado', 'monte', 'privada', 'predio', 'cultivo']
            for i, ruta in enumerate(rutas):
                prog.progress((i + 1) / len(rutas), text=os.path.basename(ruta))
                exif = proc.get_exif_data(ruta)
                lat, lon = proc.get_gps_coordinates(exif)
                fecha_foto = proc.get_datetime(exif)
                if not (lat and lon):
                    continue
                m = calc.calculate(lat, lon)
                if any(abs(h.get('abscisa_val', -9999) - m) <= 20 for h in data['hallazgos']):
                    continue
                nombre = os.path.basename(ruta).lower()
                cerca_poste = any(abs((p.get('abscisa') or -9999) - m) <= 20
                                  for p in data['potenciales'])
                explicito = any(k in nombre for k in KEYWORDS)
                if cerca_poste and not explicito:
                    continue
                tipo = ""
                if 'via' in nombre or 'vía' in nombre: tipo = "Cruce de Vía"
                elif 'caño' in nombre: tipo = "Cruce de Caño"
                elif 'tension' in nombre or 'tensión' in nombre: tipo = "Línea de media, alta o baja tensión"
                elif 'enmontado' in nombre or 'monte' in nombre: tipo = "Tramo enmontado"
                elif 'privada' in nombre or 'predio' in nombre: tipo = "Propiedad privada"
                elif 'cultivo' in nombre: tipo = "Cultivo"
                desc = f"Hallazgo generado automáticamente desde foto ({os.path.basename(ruta)})"
                if not tipo and api_key:
                    tipo_ia, desc_ia = proc.classify_image_with_ai(ruta)
                    if 'descartar' in tipo_ia.lower():
                        continue
                    tipo, desc = tipo_ia, f"{desc_ia} (Autogenerado desde foto)"
                elif not tipo:
                    continue
                data['hallazgos'].append({
                    'tipo': tipo, 'descripcion': desc, 'lat': lat, 'lon': lon,
                    'alt': None, 'abscisa_val': m, 'abscisa': calc.format_abscisa(m),
                    'fecha': fecha_foto.split(' ')[0] if fecha_foto else ''})
                nuevos += 1
            data['hallazgos'].sort(key=lambda x: x.get('abscisa_val', 0))
            st.success(f"{len(rutas)} fotos procesadas. {nuevos} hallazgos nuevos.")

# ── Tab 10: Conclusiones ──────────────────────────────────────────────────────
with tabs[9]:
    if st.button("🔄 Auto-generar Conclusiones y Recomendaciones"):
        if 'longitud_km' not in data['info'] and data['potenciales']:
            ps = sorted(data['potenciales'], key=lambda x: x.get('abscisa', 0))
            data['info']['longitud_km'] = (ps[-1].get('abscisa', 0) - ps[0].get('abscisa', 0)) / 1000.0
        cg = ConclusionGenerator(data['potenciales'], data['hallazgos'],
                                 data['rectificadores'], data['aislamientos'],
                                 st.session_state.active_inspections, data['info'])
        # El botón está ANTES de los text_area en el run, así que podemos
        # escribir sus claves de estado directamente.
        st.session_state["ta_conc"] = "\n\n".join(cg.generar_conclusiones())
        st.session_state["ta_reco"] = "\n\n".join(cg.generar_recomendaciones())
    conc = st.text_area("Conclusiones", height=260, key="ta_conc")
    reco = st.text_area("Recomendaciones", height=180, key="ta_reco")
    data['conclusiones'] = [p.strip() for p in conc.split('\n\n') if p.strip()]
    data['recomendaciones'] = [p.strip() for p in reco.split('\n\n') if p.strip()]

# ── Tab 11: Firmas ────────────────────────────────────────────────────────────
with tabs[10]:
    for rol, titulo in [('elaboro', 'Elaboró'), ('reviso', 'Revisó'), ('aprobo', 'Aprobó')]:
        st.markdown(f"**{titulo}**")
        c1, c2, c3 = st.columns(3)
        data['firmas'][rol] = {
            'nombre': c1.text_input("Nombre", value=data['firmas'][rol].get('nombre', ''), key=f"f_{rol}_n"),
            'cargo': c2.text_input("Cargo", value=data['firmas'][rol].get('cargo', ''), key=f"f_{rol}_c"),
            'empresa': c3.text_input("Empresa", value=data['firmas'][rol].get('empresa', ''), key=f"f_{rol}_e"),
        }

# ── Tab 12: Generar ───────────────────────────────────────────────────────────
with tabs[11]:
    st.subheader("Generar Informe PAP + PPM_")
    if not data['potenciales'] and not data['cips']:
        st.info("Carga al menos FASTFIELD o CIPS antes de generar.")
    if st.button("🚀 GENERAR INFORME", disabled=not (data['potenciales'] or data['cips'])):
        try:
            prog = st.progress(5, text="Iniciando...")
            info = dict(data['info'])
            info['tramo'] = re.sub(r'\s*\(?PK.*', '', info.get('tramo', '')).strip()
            info['route_id'] = st.session_state.current_route_id or ''
            if 'longitud_km' not in info and data['potenciales']:
                ps = sorted(data['potenciales'], key=lambda x: x.get('abscisa', 0))
                info['longitud_km'] = (ps[-1].get('abscisa', 0) - ps[0].get('abscisa', 0)) / 1000.0
            nombres_rect = [r.get('nombre') for r in data['rectificadores'] if r.get('nombre')]
            info['rectificadores_tgi'] = ", ".join(nombres_rect) if nombres_rect \
                else "[ESCRIBIR RECTIFICADORES TGI]"

            if info.get('tipo_inspeccion') == 'CIPS':
                gen = ReportGenerator(resource_path("CIPS EN BLANCO.xlsx"))
            else:
                gen = ReportGenerator()

            prog.progress(20, text="Información general...")
            gen.fill_general_info(info)
            if st.session_state.equipos_inspector:
                gen.fill_equipos_utilizados(st.session_state.equipos_inspector)
            gen.fill_sistema_inspeccionado(info, data['potenciales'])
            gen.fill_monitoreo(info)
            prog.progress(40, text="Potenciales...")
            gen.fill_potenciales_pap(data['potenciales'], info.get('fecha', ''))
            if data['cips']:
                try:
                    import numpy as np
                    from scipy.spatial import cKDTree
                    cips, pots = data['cips'], data['potenciales']
                    vc = [(i, [p['lat'], p['lon']]) for i, p in enumerate(cips)
                          if p.get('lat') and p.get('lon')]
                    vp = [(i, [p['lat'], p['lon']]) for i, p in enumerate(pots)
                          if p.get('lat') and p.get('lon')]
                    if vc and vp:
                        tree = cKDTree(np.array([c for _, c in vc]))
                        dist, idx = tree.query(np.array([c for _, c in vp]), k=1)
                        for (i, _), d_, ci in zip(vp, dist, idx):
                            if d_ <= 0.00018:
                                c = cips[vc[ci][0]]
                                c['vac'] = pots[i].get('vac')
                                nobs = str(pots[i].get('observaciones', ''))
                                if nobs and nobs != 'nan':
                                    obs = str(c.get('observaciones', ''))
                                    c['observaciones'] = f"{obs} | {nobs}" if obs else nobs
                except Exception:
                    pass
                gen.fill_cips(data['cips'])
            prog.progress(60, text="Gráficas y hallazgos...")
            gen.fill_graficas(data['potenciales'], info)
            hallazgos = list(data['hallazgos'])
            if info.get('tipo_inspeccion') == 'CIPS' and data['cips']:
                gen.fill_graficas_cips(data['cips'], info)
                from cips_adapter import cips_a_hallazgos
                hallazgos += cips_a_hallazgos(data['cips'])
            gen.fill_hallazgos(hallazgos, info)
            gen.fill_rectificadores(data['rectificadores'])
            gen.fill_aislamientos(data['aislamientos'])
            gen.fill_inspecciones(
                marco_h=data['inspecciones'].get('marco_h', []),
                tramos_aereos=data['inspecciones'].get('tramos_aereos', []),
                tramos_no_insp=data['inspecciones'].get('tramos_no_insp', []))
            prog.progress(80, text="Conclusiones y firmas...")
            gen.fill_conclusiones(data['conclusiones'])
            gen.fill_recomendaciones(data['recomendaciones'])
            gen.fill_firmas(data['firmas']['elaboro'], data['firmas']['reviso'],
                            data['firmas']['aprobo'])
            tmpd = tempfile.mkdtemp(prefix="tgi_out_")
            nombre = (f"PAP_REP_{info.get('tipo_ducto','')}_{info.get('tramo','')}"
                      f"_{info.get('route_id','')}_{info.get('contrato','')}_PCC_RevA.xlsx")
            pap_path = os.path.join(tmpd, nombre)
            gen.save(pap_path)
            prog.progress(90, text="Generando PPM...")
            ppm_path = os.path.join(tmpd, nombre.replace("REP", "PPM"))
            PPMGenerator().generate(info, data['potenciales'], data['aislamientos'],
                                    ppm_path, cips=data['cips'])
            with open(pap_path, 'rb') as f:
                st.session_state.informe_bytes = f.read()
            with open(ppm_path, 'rb') as f:
                st.session_state.ppm_bytes = f.read()
            st.session_state.informe_nombre = nombre
            prog.progress(100, text="¡Listo!")
            st.success("Informes generados.")
        except Exception as e:
            import traceback
            st.error(f"Error generando el informe: {e}")
            with st.expander("Detalle técnico"):
                st.code(traceback.format_exc())

    if st.session_state.informe_bytes:
        d1, d2 = st.columns(2)
        d1.download_button("⬇️ Descargar PAP", data=st.session_state.informe_bytes,
                           file_name=st.session_state.informe_nombre,
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        d2.download_button("⬇️ Descargar PPM", data=st.session_state.ppm_bytes,
                           file_name=st.session_state.informe_nombre.replace("REP", "PPM"),
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# ── Pie de página de marca ────────────────────────────────────────────────────
st.markdown("""
<hr style="border:none;border-top:1px solid #DDDDDD;margin:2.2rem 0 0.5rem;">
<div style="display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap;
            font-size:0.68rem;color:#888888;font-style:italic;">
  <span>For Internal Use Only—Not For External Distribution.
  This document is the property of PCC Integrity.
  It contains proprietary and confidential information.</span>
  <span style="font-style:normal;font-weight:700;color:#C7113A;">
    www.pccintegrity.com</span>
</div>
""", unsafe_allow_html=True)
