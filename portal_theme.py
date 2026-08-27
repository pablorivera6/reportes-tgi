# -*- coding: utf-8 -*-
"""
Capa de diseño del Portal TGI — PCC Integrity.

Separa la APARIENCIA de la lógica del portal: tokens, CSS, plantilla de gráficas
y los componentes de presentación (barra de título, ficha, veredicto, KPI, chips).

Dirección: "consola de reportes de ingeniería". El portal es la cara digital de un
informe formal que un operador de gasoducto lee para decidir; por eso el cromo es
neutro y silencioso, y el rojo PCC queda reservado para la marca y para lo que de
verdad exige atención.

Uso:
    import portal_theme as tema
    tema.aplicar(st)                     # una vez, después de set_page_config
"""

# ── Tokens ───────────────────────────────────────────────────────────────────
MARCA = "#C7113A"          # rojo PCC
MARCA_OSC = "#A00E2E"
MARCA_TINTE = "#FDF2F5"

TINTA = "#101418"          # títulos
TINTA_2 = "#3D4551"        # cuerpo
TINTA_3 = "#6B7280"        # metadatos
LINEA = "#CFD6E1"          # borde: mas marcado que el gris de la caja
LIENZO = "#FFFFFF"         # lienzo de la pagina
PANEL = "#ECEFF4"          # cajas de informacion: gris visible sobre el lienzo

# El cromo lateral es ROJO PCC: es la identidad de la empresa y así se ve en
# toda la casa. Sobre ese rojo, lo elevado es un velo blanco y lo activo es una
# pastilla blanca con texto rojo (el contraste manda mejor que otro rojo).
CROMO = "#C7113A"          # fondo del cromo lateral (rojo de marca)
CROMO_2 = "rgba(255,255,255,.14)"   # superficie elevada sobre el rojo
CROMO_BORDE = "#8E0C2A"
GRAFITO = CROMO            # compatibilidad con lo ya escrito
GRAFITO_2 = "#A50E30"

VERDE = "#0F7A46"
AMBAR = "#B45309"
ROJO = MARCA
AZUL = "#1F6FEB"
NEUTRO = TINTA

VERDE_CLARO = "#8FE6B8"    # verde/ámbar legibles sobre el rojo del cromo
AMBAR_CLARO = "#FFD79A"
VERDE_T = "#E8F4EE"
AMBAR_T = "#FEF3E2"
ROJO_T = MARCA_TINTE

# Escala de severidad DCVG (de menor a mayor), coherente con el informe
SEVERIDAD = {"Muy Pequeño": VERDE, "Pequeño": "#6E9E3E",
             "Mediano": AMBAR, "Grande": ROJO}


def tono_cumple(pct):
    """Color según el criterio NACE de −850 mV."""
    if pct is None:
        return NEUTRO
    return VERDE if pct >= 95 else (AMBAR if pct >= 85 else ROJO)


# ── CSS ──────────────────────────────────────────────────────────────────────
CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  :root {
    --marca:__MARCA__; --marca-osc:__MARCA_OSC__; --marca-tinte:__MARCA_TINTE__;
    --tinta:__TINTA__; --tinta2:__TINTA_2__; --tinta3:__TINTA_3__;
    --linea:__LINEA__; --lienzo:__LIENZO__; --panel:__PANEL__;
    --grafito:__GRAFITO__; --grafito2:__GRAFITO_2__;
    --verde:__VERDE__; --ambar:__AMBAR__; --rojo:__ROJO__;
    --r-card:10px; --r-ctrl:7px;
    --sombra:0 1px 2px rgba(16,20,24,.05), 0 1px 3px rgba(16,20,24,.04);
    --sombra-alta:0 12px 28px -14px rgba(16,20,24,.28);
  }

  /* ── Base tipográfica ─────────────────────────────────────────────────── */
  html, body, .stApp, .stApp button, .stApp input, .stApp select, .stApp textarea {
    font-family:'Inter','Segoe UI',-apple-system,'Helvetica Neue',sans-serif;
    -webkit-font-smoothing:antialiased; }
  .stApp [data-testid="stIconMaterial"] { font-family:'Material Symbols Rounded',
    'Material Symbols Outlined','Material Icons' !important; }
  .stApp { background:var(--lienzo); color:var(--tinta2); }
  /* Solo el texto corrido: los componentes con clase fijan su propio tamaño. */
  .stMain .stMarkdown p:not([class]), .stMain li { font-size:.905rem;
    line-height:1.55; color:var(--tinta2); }
  /* Las cifras se alinean en columna: dígitos de ancho fijo. */
  .num, .kpi-val, .ver-val, [data-testid="stMetricValue"],
  [data-testid="stDataFrame"] { font-variant-numeric:tabular-nums;
    font-feature-settings:'tnum' 1; }

  /* Ancho de lectura y respiración del lienzo */
  .stMainBlockContainer { max-width:1320px; padding-top:1.4rem !important;
    padding-bottom:3rem !important; }
  [data-testid="stHeader"] { background:transparent; }
  [data-testid="stToolbar"], #MainMenu, footer { display:none !important; }
  [data-testid="stDecoration"] { display:none; }
  hr { border-color:var(--linea) !important; }

  /* ── Títulos ──────────────────────────────────────────────────────────── */
  .stMain h1 { font-size:1.72rem; font-weight:800; letter-spacing:-.022em;
    color:var(--tinta) !important; margin:0; line-height:1.18; }
  .stMain h2 { font-size:1.16rem; font-weight:700; letter-spacing:-.012em;
    color:var(--tinta) !important; margin:.2rem 0 .5rem; }
  .stMain h3 { font-size:1rem; font-weight:700; letter-spacing:-.008em;
    color:var(--tinta) !important; margin:.1rem 0 .4rem; }

  /* Rótulo de sección: micro-mayúsculas con filete, como en un informe */
  .sec { display:flex; align-items:center; gap:.7rem; margin:1.7rem 0 .7rem; }
  .stApp .sec-t { font-size:.715rem; font-weight:700; letter-spacing:.09em;
    text-transform:uppercase; color:var(--tinta3); white-space:nowrap; }
  .sec-l { flex:1; height:1px; background:var(--linea); }

  /* ── Cromo lateral: navegación persistente, en el rojo de la marca ───── */
  [data-testid="stSidebar"] { background:__CROMO__ !important;
    border-right:1px solid __CROMO_BORDE__; }
  [data-testid="stSidebar"] > div:first-child { background:__CROMO__ !important;
    padding-top:1.1rem; }
  [data-testid="stSidebar"] * { color:#FFFFFF; }
  [data-testid="stSidebar"] hr { border-color:rgba(255,255,255,.22) !important;
    margin:.85rem 0; }
  .sb-marca { display:flex; align-items:center; gap:.6rem; padding:0 .35rem .2rem; }
  .sb-marca img { height:30px; }
  .sb-marca b { font-size:.95rem; font-weight:700; letter-spacing:-.01em;
    color:#FFF; display:block; line-height:1.15; }
  .sb-marca span { font-size:.7rem; color:rgba(255,255,255,.78); letter-spacing:.02em; }
  .stApp .sb-rot { font-size:.665rem; font-weight:700; letter-spacing:.1em;
    text-transform:uppercase; color:rgba(255,255,255,.68); margin:.2rem 0 .35rem .45rem; }
  /* Navegación: el paso activo es una pastilla BLANCA con texto rojo. */
  [data-testid="stSidebar"] .stButton button { width:100%; justify-content:flex-start;
    text-align:left; background:transparent !important; color:rgba(255,255,255,.88) !important;
    border:1px solid transparent !important; border-radius:var(--r-ctrl) !important;
    font-weight:500 !important; font-size:.865rem !important;
    padding:.45rem .7rem !important; box-shadow:none !important; }
  [data-testid="stSidebar"] .stButton button * { color:inherit !important; }
  [data-testid="stSidebar"] .stButton button:hover { background:rgba(255,255,255,.16) !important;
    color:#FFF !important; }
  [data-testid="stSidebar"] .stButton button[kind="primary"] {
    background:#FFFFFF !important; color:__MARCA__ !important; font-weight:700 !important;
    box-shadow:0 1px 3px rgba(0,0,0,.16) !important; }
  [data-testid="stSidebar"] .stButton button[kind="primary"] * {
    color:__MARCA__ !important; }
  /* Estado / rol: velo blanco sobre el rojo, nunca una caja de alerta */
  .sb-pill { display:flex; align-items:center; gap:.45rem; font-size:.735rem;
    color:rgba(255,255,255,.92); padding:.35rem .5rem; border-radius:6px;
    background:rgba(255,255,255,.14); margin:.3rem .1rem; line-height:1.3; }
  .sb-pill i { width:7px; height:7px; border-radius:50%; flex:none; display:block; }
  [data-testid="stSidebar"] [data-testid="stAlert"] {
    background:rgba(255,255,255,.14); border-radius:8px; }
  [data-testid="stSidebar"] [data-baseweb="radio"] label {
    color:rgba(255,255,255,.92) !important; }
  /* ── Barra de título de página ────────────────────────────────────────── */
  .barra { display:flex; align-items:flex-end; gap:1rem; flex-wrap:wrap;
    padding-bottom:.85rem; border-bottom:1px solid var(--linea); margin-bottom:.2rem; }
  .stApp .barra .via { font-size:.735rem; color:var(--tinta3); font-weight:500;
    letter-spacing:.01em; margin:0 0 .2rem; }
  .barra .via b { color:var(--tinta2); font-weight:600; }
  .barra h1 small { font-size:.92rem; font-weight:600; color:var(--tinta3);
    letter-spacing:0; margin-left:.5rem; }
  .barra .der { margin-left:auto; display:flex; align-items:center; gap:.5rem; }

  /* ── Ficha de identificación ──────────────────────────────────────────── */
  .ficha { display:grid; gap:0 1.6rem; margin:.9rem 0 .2rem;
    grid-template-columns:repeat(auto-fit, minmax(135px, 1fr)); }
  .ficha div { padding:.34rem 0; border-top:1px solid var(--linea); }
  .stApp .ficha dt { font-size:.665rem; font-weight:700; letter-spacing:.075em;
    text-transform:uppercase; color:var(--tinta3); margin:0 0 .1rem; }
  .stApp .ficha dd { font-size:.855rem; font-weight:600; color:var(--tinta); margin:0;
    font-variant-numeric:tabular-nums; }

  /* ── Veredicto: la respuesta a la pregunta del cliente ────────────────── */
  .ver { display:grid; grid-template-columns:minmax(220px,300px) 1fr; gap:0;
    background:var(--panel); border:1px solid var(--linea); border-radius:var(--r-card);
    box-shadow:var(--sombra); overflow:hidden; margin:.2rem 0 .3rem; }
  .ver-hero { padding:1.05rem 1.25rem; border-left:5px solid var(--tono);
    background:var(--tono-t); }
  .stApp .ver-rot { font-size:.665rem; font-weight:700; letter-spacing:.09em;
    text-transform:uppercase; color:var(--tinta3); margin:0 0 .15rem; }
  .stApp .ver-val { font-size:2.55rem; font-weight:800; line-height:1; letter-spacing:-.03em;
    color:var(--tono); margin:0; }
  .stApp .ver-sub { font-size:.775rem; color:var(--tinta2); margin:.3rem 0 0;
    font-weight:500; }
  .ver-apoyo { display:grid; grid-template-columns:repeat(auto-fit, minmax(118px,1fr));
    align-items:stretch; }
  .ver-apoyo > div { padding:.85rem .95rem; border-left:1px solid var(--linea); }
  .stApp .ver-apoyo dt { font-size:.655rem; font-weight:700; letter-spacing:.075em;
    text-transform:uppercase; color:var(--tinta3); margin:0 0 .22rem; }
  .stApp .ver-apoyo dd { font-size:1.3rem; font-weight:700; color:var(--tinta); margin:0;
    line-height:1.1; font-variant-numeric:tabular-nums; }
  .stApp .ver-apoyo .pie { font-size:.7rem; color:var(--tinta3); font-weight:500;
    margin:.15rem 0 0; }
  .ver-apoyo dd.alerta { color:var(--rojo); }
  .ver-apoyo dd.aviso { color:var(--ambar); }
  .ver-apoyo dd.bien { color:var(--verde); }
  @media (max-width:900px) { .ver { grid-template-columns:1fr; }
    .ver-apoyo > div { border-left:none; border-top:1px solid var(--linea); } }

  /* ── Tarjetas KPI (vistas sin veredicto único) ────────────────────────── */
  .kpi-row { display:grid; gap:.7rem; margin:.2rem 0 .3rem;
    grid-template-columns:repeat(auto-fit, minmax(158px,1fr)); align-items:stretch; }
  .kpi { background:var(--panel); border:1px solid var(--linea);
    border-left:4px solid var(--tono,#9CA3AF); border-radius:var(--r-card);
    padding:.7rem .9rem; box-shadow:var(--sombra); box-sizing:border-box;
    display:flex; flex-direction:column; justify-content:center; }
  .stApp .kpi-lbl { font-size:.665rem; font-weight:700; letter-spacing:.075em;
    text-transform:uppercase; color:var(--tinta3); margin:0 0 .18rem; }
  .stApp .kpi-val { font-size:1.6rem; font-weight:800; line-height:1.08;
    letter-spacing:-.02em; color:var(--tono,var(--tinta)); margin:0; }
  .stApp .kpi-sub { font-size:.715rem; color:var(--tinta3); margin:.14rem 0 0;
    font-weight:500; }

  /* ── Fila del listado ─────────────────────────────────────────────────── */
  .fila { background:var(--panel); border:1px solid var(--linea);
    border-radius:var(--r-card); padding:.8rem 1rem; box-shadow:var(--sombra);
    transition:box-shadow .15s ease, border-color .15s ease; }
  .fila:hover { box-shadow:var(--sombra-alta); border-color:#D3D8E0; }
  .stApp .fila-t { display:flex; align-items:center; gap:.55rem; flex-wrap:wrap;
    margin:0 0 .3rem; }
  .stApp .fila-t b { font-size:.985rem; font-weight:700; color:var(--tinta);
    letter-spacing:-.01em; }
  .fila-t .sep { color:var(--linea); }
  .stApp .fila-t .gas { font-size:.85rem; color:var(--tinta3); font-weight:500; }
  .stApp .fila-m { display:flex; gap:1.1rem; flex-wrap:wrap; margin:0;
    font-size:.775rem; color:var(--tinta3); font-weight:500; }
  .stApp .fila-m span b { color:var(--tinta2); font-weight:600;
    font-variant-numeric:tabular-nums; }

  /* ── Chips ────────────────────────────────────────────────────────────── */
  .stApp .chip { display:inline-flex; align-items:center; gap:.3rem; padding:.14rem .5rem;
    border-radius:999px; font-size:.705rem; font-weight:700; line-height:1.5;
    letter-spacing:.01em; white-space:nowrap; }
  .stApp .chip-tipo { background:var(--tinta); color:#FFF; font-size:.665rem;
    letter-spacing:.06em; padding:.16rem .46rem; }
  .chip-ok { background:__VERDE_T__; color:var(--verde); }
  .chip-warn { background:__AMBAR_T__; color:var(--ambar); }
  .chip-mal { background:var(--marca-tinte); color:var(--rojo); }
  .chip-neu { background:#EEF0F3; color:var(--tinta2); }
  .chip i { width:6px; height:6px; border-radius:50%; background:currentColor;
    display:block; flex:none; }

  /* ── Controles ────────────────────────────────────────────────────────── */
  .stMain .stButton button { border-radius:var(--r-ctrl) !important;
    font-weight:600 !important; font-size:.845rem !important;
    padding:.36rem .85rem !important; transition:all .14s ease; }
  .stMain .stButton button[kind="primary"] { background:var(--marca) !important;
    color:#FFF !important; border:1px solid var(--marca) !important;
    box-shadow:0 1px 2px rgba(199,17,58,.25) !important; }
  .stMain .stButton button[kind="primary"]:hover { background:var(--marca-osc) !important;
    border-color:var(--marca-osc) !important; }
  .stMain .stButton button[kind="secondary"] { background:var(--panel) !important;
    color:var(--tinta2) !important; border:1px solid #D7DBE2 !important; }
  .stMain .stButton button[kind="secondary"]:hover { border-color:var(--marca) !important;
    color:var(--marca) !important; background:var(--marca-tinte) !important; }
  [data-testid="stDownloadButton"] button, .stMain .stLinkButton a {
    background:var(--panel) !important; color:var(--marca) !important;
    border:1px solid var(--marca) !important; border-radius:var(--r-ctrl) !important;
    font-weight:600 !important; font-size:.845rem !important; }
  [data-testid="stDownloadButton"] button:hover, .stMain .stLinkButton a:hover {
    background:var(--marca-tinte) !important; }
  /* Deshabilitado: se ve que la acción existe, pero que aún no está disponible. */
  .stMain .stButton button:disabled,
  .stMain [data-testid="stDownloadButton"] button:disabled {
    background:#EDEFF2 !important; color:#98A0AB !important;
    border:1px solid #E4E7EC !important; box-shadow:none !important; }
  /* Foco visible: se navega con teclado */
  .stApp button:focus-visible, .stApp a:focus-visible, .stApp input:focus-visible {
    outline:2px solid var(--marca) !important; outline-offset:2px !important; }
  .stMain [data-baseweb="select"] > div { border-radius:var(--r-ctrl) !important;
    border-color:#D7DBE2 !important; background:var(--panel) !important; }
  /* Micro-mayúscula SOLO en la etiqueta del campo; las opciones van normales. */
  .stMain [data-testid="stWidgetLabel"] p { font-size:.72rem !important;
    font-weight:700 !important; letter-spacing:.05em; text-transform:uppercase;
    color:var(--tinta3) !important; }
  .stMain [data-baseweb="radio"] label, .stMain [data-baseweb="checkbox"] label {
    text-transform:none !important; font-size:.845rem !important;
    font-weight:500 !important; letter-spacing:0 !important;
    color:var(--tinta2) !important; }

  /* ── Pasos del flujo (st.tabs) ───────────────────────────────────────── */
  /* Envuelve en varias filas: nunca se esconde un paso (antes 'Generar',
     el paso final, quedaba fuera de pantalla por debajo de ~1440 px). */
  .stTabs [data-baseweb="tab-list"] { flex-wrap:wrap !important; gap:.1rem .35rem;
    border-bottom:1px solid var(--linea); overflow:visible !important; }
  .stTabs [data-baseweb="tab"] { color:var(--tinta3) !important; font-weight:600;
    font-size:.83rem; padding:.42rem .6rem !important; height:auto !important;
    white-space:nowrap; }
  .stTabs [data-baseweb="tab"]:hover { color:var(--tinta) !important; }
  .stTabs [aria-selected="true"] { color:var(--marca) !important; font-weight:700; }
  .stTabs [data-baseweb="tab-highlight"] { background:var(--marca) !important; }
  .stTabs [data-baseweb="tab-border"] { display:none !important; }
  /* Marca de paso surtido: un punto antes de la etiqueta. */
  .stTabs [data-baseweb="tab"] .pt { display:inline-block; width:6px; height:6px;
    border-radius:50%; margin-right:.4rem; vertical-align:middle;
    background:var(--linea); }
  /* ── Botón terciario: acciones secundarias y destructivas ────────────── */
  .stMain .stButton button[kind="tertiary"] { background:transparent !important;
    color:var(--tinta3) !important; border:1px solid transparent !important;
    font-weight:600 !important; }
  .stMain .stButton button[kind="tertiary"]:hover { color:var(--rojo) !important;
    background:var(--marca-tinte) !important; border-color:#F0CDD5 !important; }
  /* ── Panel de estado del trabajo (cromo lateral) ─────────────────────── */
  .sb-item { display:flex; align-items:center; gap:.5rem; padding:.28rem .5rem;
    border-radius:6px; font-size:.775rem; color:rgba(255,255,255,.9); line-height:1.35; }
  .sb-item i { width:7px; height:7px; border-radius:50%; flex:none; display:block; }
  .sb-item span { margin-left:auto; font-weight:700; color:#FFF;
    font-variant-numeric:tabular-nums; }
  .sb-item.apagado { color:rgba(255,255,255,.6); }
  .sb-item.apagado span { color:rgba(255,255,255,.6); font-weight:600; }
  .sb-veredicto { margin:.55rem .1rem .2rem; padding:.5rem .6rem; border-radius:8px;
    background:rgba(255,255,255,.16); border-left:3px solid var(--tono,#FFF);
    font-size:.755rem; color:rgba(255,255,255,.92); line-height:1.35; }
  .sb-veredicto b { display:block; color:#FFF; font-size:.8rem; margin-bottom:.1rem; }
  /* Cajas de informacion creadas con st.container(border=True, key="caja_..."):
     Streamlit las deja con fondo transparente y se funden con el lienzo. */
  .stApp [class*="st-key-caja"] { background:var(--panel) !important;
    border:1px solid var(--linea) !important; border-radius:var(--r-card) !important;
    padding:.85rem 1rem !important; }
  /* ── Datos ────────────────────────────────────────────────────────────── */
  [data-testid="stDataFrame"] { border:1px solid var(--linea) !important;
    border-radius:var(--r-card) !important; overflow:hidden; box-shadow:var(--sombra); }
  [data-testid="stElementContainer"]:has(> [data-testid="stPlotlyChart"]),
  [data-testid="stElementContainer"]:has(> [data-testid="stDeckGlJsonChart"]) {
    background:var(--panel); border:1px solid var(--linea);
    border-radius:var(--r-card); padding:.55rem; box-shadow:var(--sombra); }
  [data-testid="stMetricValue"] { font-size:1.5rem; font-weight:700;
    color:var(--tinta); letter-spacing:-.02em; }
  [data-testid="stMetricLabel"] p { font-size:.68rem !important; font-weight:700;
    letter-spacing:.075em; text-transform:uppercase; color:var(--tinta3) !important; }
  [data-testid="stExpander"] { border:1px solid var(--linea) !important;
    border-radius:var(--r-card) !important; background:var(--panel); }

  /* ── Pie ──────────────────────────────────────────────────────────────── */
  .stApp .pie-app { display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap;
    color:var(--tinta3); font-size:.735rem; border-top:1px solid var(--linea);
    margin-top:2.4rem; padding-top:.85rem; }
  .pie-app b { color:var(--marca); font-weight:700; }
</style>
"""

# Markdown corta el bloque HTML en la primera linea vacia: el CSS va compacto.
CSS = "\n".join(l for l in CSS.split("\n") if l.strip())

# El CSS lleva porcentajes literales (50%, 100%), asi que los tokens se
# sustituyen por nombre en vez de usar formateo con %.
for _k, _v in (("MARCA", MARCA), ("MARCA_OSC", MARCA_OSC), ("MARCA_TINTE", MARCA_TINTE),
               ("TINTA_2", TINTA_2), ("TINTA_3", TINTA_3), ("TINTA", TINTA),
               ("LINEA", LINEA), ("LIENZO", LIENZO), ("PANEL", PANEL),
               ("GRAFITO_2", GRAFITO_2), ("GRAFITO", GRAFITO),
               ("CROMO_BORDE", CROMO_BORDE), ("CROMO_2", CROMO_2), ("CROMO", CROMO),
               ("VERDE_CLARO", VERDE_CLARO), ("AMBAR_CLARO", AMBAR_CLARO),
               ("VERDE_T", VERDE_T), ("AMBAR_T", AMBAR_T),
               ("VERDE", VERDE), ("AMBAR", AMBAR), ("ROJO", ROJO)):
    CSS = CSS.replace("__%s__" % _k, _v)


# ── Gráficas: una sola plantilla para que todas se lean igual ────────────────
def _registrar_plantilla_plotly():
    try:
        import plotly.graph_objects as go
        import plotly.io as pio
    except Exception:
        return
    eje = dict(showgrid=True, gridcolor="#EDEFF3", gridwidth=1, zeroline=False,
               linecolor=LINEA, ticks="outside", tickcolor=LINEA, ticklen=4,
               tickfont=dict(size=11, color=TINTA_3),
               title=dict(font=dict(size=11.5, color=TINTA_3)))
    pio.templates["pcc"] = go.layout.Template(layout=dict(
        font=dict(family="Inter, 'Segoe UI', sans-serif", size=12, color=TINTA_2),
        paper_bgcolor=PANEL, plot_bgcolor=PANEL,
        colorway=[TINTA_2, MARCA, AZUL, AMBAR, VERDE, "#8B5CF6"],
        xaxis=eje, yaxis=eje,
        margin=dict(t=16, b=8, l=8, r=12),
        hoverlabel=dict(bgcolor=TINTA, font=dict(family="Inter", size=12,
                                                 color="#FFF"), bordercolor=TINTA),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0,
                    font=dict(size=11.5, color=TINTA_3), bgcolor="rgba(0,0,0,0)"),
        title=dict(font=dict(size=13.5, color=TINTA)),
    ))
    pio.templates.default = "pcc"


def aplicar(st):
    """Inyecta el CSS y fija la plantilla de gráficas. Llamar una sola vez."""
    st.markdown(CSS, unsafe_allow_html=True)
    _registrar_plantilla_plotly()


# ── Componentes de presentación ─────────────────────────────────────────────
def chip(texto, tono="neu", punto=False):
    clase = {"ok": "chip-ok", "warn": "chip-warn", "mal": "chip-mal",
             "neu": "chip-neu", "tipo": "chip-tipo"}.get(tono, "chip-neu")
    p = "<i></i>" if punto else ""
    return f"<span class='chip {clase}'>{p}{texto}</span>"


def seccion(st, titulo):
    """Rótulo de sección con filete."""
    st.markdown(f"<div class='sec'><span class='sec-t'>{titulo}</span>"
                f"<span class='sec-l'></span></div>", unsafe_allow_html=True)


def barra_titulo(st, titulo, via="", sufijo="", derecha=""):
    """Encabezado de página: ruta, título y estado/acción a la derecha."""
    _via = f"<p class='via'>{via}</p>" if via else ""
    _suf = f"<small>{sufijo}</small>" if sufijo else ""
    st.markdown(
        f"<div class='barra'><div>{_via}<h1>{titulo}{_suf}</h1></div>"
        f"<div class='der'>{derecha}</div></div>", unsafe_allow_html=True)


def ficha(st, campos):
    """Datos de identificación del informe. campos = [(etiqueta, valor), ...]
    Los campos vacíos se muestran con raya: en un informe formal el dato que
    falta es información, no algo que convenga esconder."""
    items = "".join(f"<div><dt>{k}</dt><dd>{v if v not in (None, '') else '—'}</dd></div>"
                    for k, v in campos)
    if items:
        st.markdown(f"<dl class='ficha'>{items}</dl>", unsafe_allow_html=True)


def veredicto(st, rotulo, valor, tono, sub, apoyo):
    """Panel principal: la conclusión primero, el detalle después.
    apoyo = [(etiqueta, valor, pie, clase)] con clase en '', 'bien','aviso','alerta'
    """
    tinte = {VERDE: VERDE_T, AMBAR: AMBAR_T, ROJO: ROJO_T}.get(tono, "#F4F5F7")
    cel = "".join(
        f"<div><dt>{k}</dt><dd class='{cl}'>{v}</dd>"
        + (f"<p class='pie'>{pie}</p>" if pie else "") + "</div>"
        for k, v, pie, cl in apoyo)
    st.markdown(
        f"<div class='ver' style='--tono:{tono};--tono-t:{tinte}'>"
        f"<div class='ver-hero'><p class='ver-rot'>{rotulo}</p>"
        f"<p class='ver-val'>{valor}</p><p class='ver-sub'>{sub}</p></div>"
        f"<dl class='ver-apoyo'>{cel}</dl></div>", unsafe_allow_html=True)


def kpi_row(st, items):
    """Fila de indicadores. items = [(etiqueta, valor, tono, pie), ...]"""
    cards = "".join(
        f"<div class='kpi' style='--tono:{t}'><p class='kpi-lbl'>{lbl}</p>"
        f"<p class='kpi-val'>{val}</p><p class='kpi-sub'>{sub or '&nbsp;'}</p></div>"
        for lbl, val, t, sub in items)
    st.markdown(f"<div class='kpi-row'>{cards}</div>", unsafe_allow_html=True)


def estado_trabajo(st, items, veredicto=None):
    """Panel de estado del trabajo en curso (cromo lateral).
    items = [(etiqueta, valor, activo)] · veredicto = (titulo, detalle, tono)"""
    filas = "".join(
        "<div class='sb-item%s'><i style='background:%s'></i>%s<span>%s</span></div>"
        % ("" if act else " apagado",
           (VERDE_CLARO if act else "rgba(255,255,255,.38)"), lbl, val)
        for lbl, val, act in items)
    st.markdown(filas, unsafe_allow_html=True)
    if veredicto:
        tit, det, tono = veredicto
        # sobre el rojo del cromo, el verde/ámbar oscuros no se leen
        tono = {VERDE: VERDE_CLARO, AMBAR: AMBAR_CLARO, ROJO: "#FFFFFF"}.get(tono, tono)
        st.markdown(f"<div class='sb-veredicto' style='--tono:{tono}'>"
                    f"<b>{tit}</b>{det}</div>", unsafe_allow_html=True)


def pie_pagina(st):
    st.markdown(
        "<div class='pie-app'><span><i>For Internal Use Only — Not For External "
        "Distribution. Property of PCC Integrity.</i></span>"
        "<b>www.pccintegrity.com</b></div>", unsafe_allow_html=True)
