# App web Reportes TGI en Streamlit Cloud — Diseño

Fecha: 2026-07-17

## Contexto y motivación

La distribución de la app de escritorio fracasó en la práctica: el ingeniero en
Windows no pudo abrirla. Decisión del usuario: desplegar la app en la nube.
Elección: **Streamlit + Streamlit Community Cloud**, porque el usuario ya opera
`proceso-cips` con ese stack (repo GitHub → share.streamlit.io, secrets) y toda
la lógica de negocio de esta app ya está separada de la interfaz.

## Decisiones del usuario

- **Acceso:** solo el equipo PCC, con login — repo privado + app compartida por
  lista de correos autorizados (Google login). Es la única app privada del cupo
  gratuito de la cuenta (proceso-cips es pública).
- **Alcance v1:** TODO el flujo de la app de escritorio (las 8 secciones,
  incluidas fotos con IA e inspecciones especiales).

## Arquitectura

**Un archivo nuevo** (`streamlit_app.py`) sobre el motor existente, que no se toca:

| Capa | Módulos | Estado |
|---|---|---|
| UI web (nueva) | `streamlit_app.py` | Se escribe |
| UI escritorio | `app.py` (PyQt6) | Queda igual; ambas UIs comparten el motor |
| Motor | `readers.py`, `generator.py`, `conclusions.py`, `geo_utils.py`, `photo_utils.py`, `ppm_generator.py`, `cips_lrs.py`, `cips_infra.py`, `cips_adapter.py`, `mod_unificar.py`, `mod_cips_lrs.py` | Se reutiliza tal cual |
| Assets | Plantillas xlsx, KMZ, `shapefiles.zip`, Excel infra/equipos/OT | Se reutilizan tal cual |

### Estructura de la UI web

- **Sidebar:** branding PCC (como proceso-cips), estado del KMZ, botón global
  "GENERAR INFORME".
- **st.tabs** replicando las secciones de escritorio:
  1. Datos Generales — campos de info + autollenado desde "Infraestrutura TGI"
     y "consolidado OT" al escribir el tramo; equipos del inspector desde
     "Listado equipos TGI".
  2. Carga de archivos — FASTFIELD (multi), EQUIPOS, Rectificadores,
     Aislamientos; selector CIPS Empresa→Distrito→Tramo + carga CIPS (motor LRS).
  3. Potenciales PAP (tabla), 4. CIPS (tabla), 5. Hallazgos (tabla),
  6. Rectificadores (tabla), 7. Insp. Especiales (checkboxes),
  8. Aislamientos (tabla), 9. Fotos IA (uploader de imágenes múltiples),
  10. Conclusiones (auto-generar + edición), 11. Firmas.
- **Estado:** `st.session_state['data']` con el MISMO dict que usa la app de
  escritorio (`info`, `potenciales`, `cips`, `hallazgos`, `rectificadores`,
  `aislamientos`, `inspecciones`, `conclusiones`, `recomendaciones`, `firmas`),
  de modo que el motor recibe estructuras idénticas.
- **Archivos:** `st.file_uploader` → guardar a tmp → pasar rutas a los readers
  existentes (reciben rutas de archivo).
- **Fotos:** el navegador no sube carpetas; se suben imágenes múltiples. EXIF y
  clasificación Gemini con la lógica existente de `photo_utils`.
- **Generar:** botón que ejecuta la secuencia del `WorkerThread` de escritorio
  (misma orquestación, síncrona) con `st.progress`; produce PAP y PPM en memoria
  y ofrece **dos `st.download_button`**.
- **KMZ:** carga al arranque con `st.cache_resource` (igual que el auto-load de
  escritorio, ya reparado).

### Secretos y acceso

- **Gemini API key:** en `st.secrets['gemini']['api_key']` — deja de pedirse en
  pantalla. Si no está configurada, la clasificación IA se omite (mismo
  comportamiento que escritorio sin llave).
- **Acceso:** app privada; invitación por correo desde el panel de Streamlit
  Cloud. Sin login propio en el código.

### Dependencias

`requirements.txt` (raíz, lo lee Streamlit Cloud): streamlit + motor
(pandas, numpy, scipy, openpyxl, pyproj, shapely, pyshp, scikit-learn, pillow,
google-generativeai). **Sin PyQt6** (no instala en el contenedor y no se usa).
PyQt6 pasa a `requirements-desktop.txt`; los scripts de build instalan ambos.

### Despliegue

1. Repo privado `pablorivera6/reportes-tgi` en GitHub (push del repo local).
2. share.streamlit.io → New app → repo + `streamlit_app.py`.
3. Pegar secrets (plantilla en `DEPLOY.md`).
4. Share → invitar correos del equipo.

Pasos 2–4 los hace el usuario en su navegador (requieren su cuenta); `DEPLOY.md`
los documenta con exactitud.

## Manejo de errores

- Cada acción de carga envuelta en try/except con `st.error` claro (equivalente
  de los QMessageBox).
- Validaciones previas a generar: hay potenciales cargados, tramo definido.
- Si falta el shapefile del tramo CIPS: error claro sin procesar.

## Pruebas

- La suite del motor (12 tests) queda intacta.
- Nuevos tests con `streamlit.testing.v1.AppTest`: la app monta sin excepciones,
  las tabs existen, el flujo básico (estado inicial → sin crashes) pasa.
- Verificación manual final en la URL desplegada.

## Límites conocidos (plan gratuito)

- La app "duerme" tras días sin uso; el primer acceso tarda ~1 min.
- 1 GB de RAM (suficiente: el motor no usa librerías pesadas).
- Subida de archivos hasta 200 MB por archivo (de sobra).
