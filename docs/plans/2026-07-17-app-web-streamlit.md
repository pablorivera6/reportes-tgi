# App web Streamlit Implementation Plan

**Goal:** Interfaz web Streamlit (`streamlit_app.py`) sobre el motor existente, con el flujo completo de la app de escritorio, lista para desplegar en Streamlit Community Cloud como app privada.

**Architecture:** Un archivo de UI nuevo que replica las secciones de PyQt como `st.tabs`, con `st.session_state['data']` usando el MISMO esquema de dict que la app de escritorio, de modo que readers/generator/motor CIPS se llaman sin cambios. La generación porta la secuencia del `WorkerThread` de forma síncrona con `st.progress` y entrega PAP/PPM por `st.download_button`.

**Tech Stack:** Streamlit ≥1.32, streamlit.testing.v1.AppTest para humo, gh CLI para el repo privado.

**Rama:** `feat/web-streamlit` desde `feat/cips-lrs`.

---

### Task 1: Rama + split de requirements
- `git checkout -b feat/web-streamlit`
- `requirements.txt` (cloud): streamlit>=1.32 + motor, SIN PyQt6.
- `requirements-desktop.txt`: `-r requirements.txt` + PyQt6.
- `build_mac.sh`/`build_windows.bat`: instalar `-r requirements-desktop.txt`.
- Commit.

### Task 2: `streamlit_app.py` — scaffolding + estado
- `st.set_page_config` (wide, título "PCC – Reportes TGI").
- CSS corporativo (adaptación del de proceso-cips, rojo PCC).
- `init_state()`: `st.session_state.data` con el dict exacto de escritorio
  (`info`, `potenciales`, `cips`, `hallazgos`, `rectificadores`, `aislamientos`,
  `inspecciones`, `conclusiones`, `recomendaciones`, `firmas`) +
  `active_inspections` + `equipos_inspector`.
- `@st.cache_resource cargar_kmz()` → KMZPipelineLoader del KMZ bundled;
  `@st.cache_resource cargar_infra_tramos()` → InfraTramos().
- `_tmp_files(uploaded_files)` helper: guarda file_uploaders a tmp y devuelve rutas.
- Sidebar: branding + estado KMZ + progreso.

### Task 3: Tab Datos Generales
- Campos de `info` (gasoducto, tramo, tipo ducto, contrato, OT, contratista,
  fecha, inspector, serial, fecha calibración, diámetro, recubrimiento, ciclo,
  tipo_inspeccion selectbox PAP/CIPS/DCVG).
- Port de `autofill_from_infrastructure`, `autofill_ot_km`,
  `get_equipos_for_inspector` como funciones puras (mismas rutas de assets vía
  `resource_path`), disparadas al cambiar tramo/inspector.

### Task 4: Cargas de archivos (tab Archivos)
- FASTFIELD multi → `FastFieldReader.read` por archivo; si hay varios tramos,
  `st.multiselect` para elegir (equivalente del TramoSelectorDialog); acumula en
  `data['potenciales']`; autollenados; post-proceso marco_h/tramos aéreos
  (portar el bloque de `load_fastfield`).
- EQUIPOS → `EquipoReader` + abscisas de hallazgos con AbscisaCalculator (portar
  lógica de `load_equipo`).
- Rectificadores → `RectificadorReader`.
- Aislamientos → `AislamientoReader.read_files`.
- CIPS: selectboxes Empresa→Distrito→Tramo desde InfraTramos (cascada como la
  UI de escritorio) → `procesar_cips_lrs` + `lrs_df_a_cips_dicts` → `data['cips']`.

### Task 5: Tabs de tablas + especiales
- Potenciales PAP, CIPS, Hallazgos, Rectificadores, Aislamientos: `st.dataframe`
  desde `data` (columnas como las tablas de escritorio).
- Insp. Especiales: 6 checkboxes → `active_inspections`.

### Task 6: Tab Fotos IA
- Uploader múltiple de imágenes → tmp → port de la lógica de `load_fotos`
  (EXIF GPS/fecha, dedupe ±20 m, keywords, Gemini si hay
  `st.secrets['gemini']['api_key']`), con `st.progress`.

### Task 7: Conclusiones y Firmas
- Botón auto-generar → `ConclusionGenerator` (mismo `collect_info` portado);
  `st.text_area` editables para conclusiones/recomendaciones.
- Firmas: 3x (nombre, cargo, empresa).

### Task 8: Generar informe
- Validaciones (potenciales o cips presentes; tramo definido).
- Port de la secuencia `WorkerThread.run` (elige plantilla CIPS/estándar,
  fill_* en orden, spatial-merge CIPS-PAP con cKDTree, save PAP a tmp,
  PPMGenerator a tmp) con `st.progress`.
- Leer bytes → 2 `st.download_button` (PAP, PPM) con nombres como escritorio
  (`PAP_REP_..._RevA.xlsx` / `PPM_...`).

### Task 9: Tests de humo (AppTest)
- `tests/test_web_app.py`: `AppTest.from_file('streamlit_app.py')` monta sin
  excepciones; tabs presentes; session_state.data inicializado.
- Suite completa en verde.

### Task 10: Deploy
- `DEPLOY.md`: pasos exactos share.streamlit.io + plantilla de secrets + invitar
  correos.
- `gh repo create pablorivera6/reportes-tgi --private` + push ramas.
- Entregar al usuario los 3 pasos de navegador.
