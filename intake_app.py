"""
Carga de campo TGI — formulario para técnicos (PCC Integrity).

App SEPARADA y simple: el técnico elige tramo + tipo de inspección + fecha,
sube cada archivo en su casilla y envía. Todo se guarda ORGANIZADO en la nube
(Supabase Storage + espejo opcional a SharePoint) y queda como "carga pendiente"
para la app de procesamiento. Así se acaba el desorden de subir a SharePoint a mano.

Despliegue: Streamlit Cloud, mismo repo, main file = intake_app.py.
Secrets: [supabase] url + service_key ; [intake] password ; [sharepoint] flow_url (opcional).
"""
import os
import base64

import streamlit as st

from generator import resource_path
import db
import sharepoint


# ── Marca ────────────────────────────────────────────────────────────────────
def _b64_img(nombre):
    ruta = resource_path(nombre)
    if os.path.exists(ruta):
        with open(ruta, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""


_LOGO_BLANCO = _b64_img("logo_white.png")
_ICONO = resource_path("logo.png")

st.set_page_config(page_title="PCC · Carga de campo TGI",
                   page_icon=_ICONO if os.path.exists(_ICONO) else "📤",
                   layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
  html, body, .stApp, .stApp * { font-family: Calibri, 'Segoe UI',
    -apple-system, 'Helvetica Neue', sans-serif; }
  .stApp [data-testid="stIconMaterial"] { font-family:'Material Symbols Rounded',
    'Material Symbols Outlined','Material Icons' !important; }
  .stApp { background:#FFFFFF; }
  h2,h3 { color:#C7113A !important; font-weight:700 !important; }
  .stButton > button { background:#C7113A !important; color:#FFFFFF !important;
    border:none !important; border-radius:6px !important; font-weight:700 !important; }
  .stButton > button:hover { background:#A50E30 !important; }
  .pcc-hero { background:#C7113A; color:#FFFFFF; border-radius:8px;
    padding:1.1rem 1.6rem; margin-bottom:1rem; display:flex; align-items:center;
    gap:1.2rem; }
  .pcc-hero h1 { margin:0; font-size:1.4rem; font-weight:800; color:#FFF !important; }
  .pcc-hero p { margin:0.15rem 0 0; opacity:0.9; font-size:0.88rem; }
  .slot-req { color:#C7113A; font-weight:700; }
  #MainMenu, footer { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

_logo = (f'<img src="data:image/png;base64,{_LOGO_BLANCO}" style="height:42px;">'
         if _LOGO_BLANCO else '')


# ── Candado (técnicos) ───────────────────────────────────────────────────────
def _pwd():
    try:
        return str(st.secrets.get("intake", {}).get("password", ""))
    except Exception:
        return ""


_PWD = _pwd()
if _PWD and not st.session_state.get("intake_ok"):
    st.markdown(f"""<div class="pcc-hero">{_logo}<div><h1>Carga de campo TGI_</h1>
      <p>Acceso técnicos · PCC Integrity</p></div></div>""", unsafe_allow_html=True)
    with st.form("intake_login"):
        clave = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            import hmac
            if hmac.compare_digest(clave, _PWD):
                st.session_state.intake_ok = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta.")
    st.stop()


# ── Lista de tramos (para el selector) ───────────────────────────────────────
@st.cache_data(show_spinner=False)
def _tramos_disponibles():
    try:
        from cips_infra import InfraTramos
        infra = InfraTramos()
        nombres = set()
        for emp in infra.empresas():
            try:
                for t in infra.tramos(emp):
                    if t:
                        nombres.add(str(t))
            except Exception:
                continue
        return sorted(nombres)
    except Exception:
        return []


# Casillas por tipo de inspección: (clave, etiqueta, requerido, tipos_archivo)
_XLS = ["xlsx", "xls"]
_IMG = ["jpg", "jpeg", "png", "heic"]
CATEGORIAS = {
    "CIPS": [
        ("cips", "Archivo CIPS (iBTVM)", True, _XLS),
        ("fotos", "Fotos de la inspección", False, _IMG),
    ],
    "PAP": [
        ("huellas", "Archivo de huellas (FastField)", True, _XLS),
        ("equipos", "Listado de equipos (opcional)", False, _XLS),
        ("rectificador", "Rectificador URPC (opcional)", False, _XLS),
        ("aislamientos", "Aislamientos FastField (opcional)", False, _XLS),
        ("fotos", "Fotos de la inspección", False, _IMG),
    ],
    "DCVG": [
        ("dcvg", "FastField DCVG", True, _XLS),
        ("resistividades", "Resistividades", True, _XLS),
        ("logger", "Data cruda del logger", True, _XLS),
        ("fotos", "Fotos de la inspección", False, _IMG),
    ],
}


# ── Formulario ───────────────────────────────────────────────────────────────
st.markdown(f"""<div class="pcc-hero">{_logo}
  <div><h1>Carga de campo TGI_</h1>
  <p>Sube la información de tu inspección · se organiza sola en la nube</p></div>
</div>""", unsafe_allow_html=True)

if not db.disponible(write=True):
    st.error("La nube no está configurada (falta `[supabase] service_key`). "
             "Avisa a la oficina PCC.")
    st.stop()

if st.session_state.get("carga_ok"):
    st.success(st.session_state.carga_ok)
    st.session_state.carga_ok = None
    if st.button("➕ Registrar otra carga"):
        st.rerun()
    st.stop()

col1, col2 = st.columns(2)
tramos = _tramos_disponibles()
if tramos:
    tramo = col1.selectbox("Tramo *", ["— elige —"] + tramos, index=0)
    tramo = "" if tramo == "— elige —" else tramo
else:
    tramo = col1.text_input("Tramo *")
tipo = col2.selectbox("Tipo de inspección *", ["CIPS", "PAP", "DCVG"], index=0)

col3, col4 = st.columns(2)
import datetime as _dt
fecha = col3.date_input("Fecha de inspección *", value=_dt.date.today())
tecnico = col4.text_input("Tu nombre (técnico) *")

st.divider()
st.markdown(f"**Archivos para inspección {tipo}** "
            f"<span class='slot-req'>(*) obligatorio</span>", unsafe_allow_html=True)

uploads = {}
for clave, etiqueta, requerido, tipos in CATEGORIAS[tipo]:
    label = f"{etiqueta}{' *' if requerido else ''}"
    uploads[clave] = st.file_uploader(label, type=tipos,
                                      accept_multiple_files=True, key=f"up_{tipo}_{clave}")

nota = st.text_area("Nota / observaciones (opcional)", height=70)

# validación
_faltan_req = [et for (cl, et, req, _t) in CATEGORIAS[tipo] if req and not uploads.get(cl)]
_falta_meta = not (tramo and tecnico)

if st.button("📤 Enviar carga", disabled=(_falta_meta or bool(_faltan_req))):
    try:
        archivos_por_categoria = {
            clave: [(uf.name, uf.getbuffer().tobytes()) for uf in (files or [])]
            for clave, files in uploads.items() if files
        }
        with st.spinner("Subiendo y organizando en la nube..."):
            carga_id, sp_ok, n = db.guardar_carga(
                tramo, tipo, fecha, tecnico, archivos_por_categoria, nota)
        msg = (f"✅ Carga enviada: {n} archivo(s) de **{tramo}** ({tipo}). "
               f"Ya quedó organizada para la oficina.")
        if sharepoint.disponible():
            msg += ("  \nSharePoint: " + ("copiado ✓" if sp_ok else
                    "⚠️ no se pudo copiar (Supabase sí guardó)"))
        st.session_state.carga_ok = msg
        st.rerun()
    except Exception as e:
        st.error(f"No se pudo enviar la carga: {e}")

if _falta_meta:
    st.caption("Completa **tramo** y **tu nombre**.")
elif _faltan_req:
    st.caption("Faltan archivos obligatorios: " + ", ".join(_faltan_req))
