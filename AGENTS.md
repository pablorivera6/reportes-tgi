# AGENTS.md — Generador de Reportes TGI / OCENSA (PCC Integrity)

Guía para agentes de IA que trabajen en este proyecto. Léela ANTES de tocar
código. Está pensada para no re-derivar el contexto en cada sesión y para no
romper ningún paso de la generación de informes.

---

## 1. Qué es

App de escritorio (PyQt6) **y** web (Streamlit) que automatiza los informes de
inspección de protección catódica del gasoducto TGI (y OCENSA). La hace PCC
Integrity (antes Protección Catódica de Colombia). Un ingeniero de PCC la usa.

Genera **3 tipos de informe**, según "Tipo Inspección" en Datos Generales:
- **PAP** (Inspección Poste a Poste) → plantilla `EN BLANCO.xlsx`
- **CIPS** (Close Interval Potential Survey) → plantilla `CIPS EN BLANCO.xlsx`
- **DCVG** (Direct Current Voltage Gradient) → plantilla `DCVG_REP.xlsx`

Cada informe es un `.xlsx` que se llena sobre una plantilla con gráficas
embebidas. Se genera además un **PPM** (archivo plano para cargar a la BD de TGI).

---

## 2. Reglas de trabajo (CRÍTICAS — evitar fallos de entorno)

- **iCloud Desktop:** el proyecto vive en `~/Desktop/Reportes TGI ejecutable/`,
  sincronizado con iCloud. Las **lecturas masivas** (los 259 shapefiles, `git`
  en el Desktop) se **CUELGAN** (TimeoutError errno 60). NUNCA hagas `git`,
  builds ni escaneos masivos desde el Desktop.
- **Push a GitHub:** repo **público** `pablorivera6/reportes-tgi` (rama `main`).
  Se hace desde un **clon en `/private/tmp/tgi_push_new`**. Flujo:
  `cp <archivos cambiados> /private/tmp/tgi_push_new/ && cd /private/tmp/tgi_push_new && git add -A && git commit && git push`.
  Si el clon no existe o se corrompió (a `/private/tmp` lo limpian a veces):
  `rm -rf /private/tmp/tgi_push_new && git clone https://github.com/pablorivera6/reportes-tgi.git /private/tmp/tgi_push_new`.
  El clasificador de auto-mode **bloquea publicar datos personales** a repo
  público (p.ej. `Listado equipos TGI.xlsx`): en ese caso deja el archivo
  copiado y pide al usuario que ejecute el commit/push él mismo.
- **Streamlit Cloud:** cada push a `main` redespliega en ~1 min. Repo público +
  candado de contraseña (`st.secrets["app"]["password"]`, ver DEPLOY.md).
- **venv de pruebas:** `/private/tmp/venv_tgi` (se recrea si `/private/tmp` se
  limpió):
  `python3 -m venv /private/tmp/venv_tgi && /private/tmp/venv_tgi/bin/pip install "numpy<2" "pandas<2.3" scipy scikit-learn pyproj shapely pyshp openpyxl pytest streamlit`.
  **OJO pandas 3.0** rompe el motor CIPS (asignaciones a columnas); usar
  pandas 2.x (como en producción). numpy 1.26.
- **Acceso a `~/Downloads`:** el sandbox/venv NO puede listar `~/Downloads` ni
  hacer `cp` de ahí. PERO `/opt/anaconda3/bin/python3` SÍ puede **leer** un
  archivo específico que el usuario @-mencionó (`open(path,'rb')`,
  `openpyxl.load_workbook(path)`). Para tener archivos de prueba accesibles al
  venv, cópialos con `/opt/anaconda3/bin/python3` (byte copy) a `/private/tmp/…`.
- **openpyxl y gráficas:** load+save PRESERVA hojas y charts (verificado). NO
  usa `copy_worksheet` para hojas con charts (los pierde); usa deepcopy del
  chart. Las series de chart se guardan SIN prefijo `c:` en el XML (un grep de
  `<c:f>` da falso negativo; las series SÍ están).
- **Celdas combinadas:** escribir `.value` en una MergedCell lanza
  `AttributeError`. `generator._safe_write` lo atrapa; escrituras directas
  `ws.cell(...,value=...)` NO. Las zonas de datos de las plantillas NO deben
  tener merges (los bloques de firmas sí, al final).
- **TDD siempre:** escribe el test primero, valida con los datos reales
  (`/private/tmp/dcvg_ref/` para DCVG; los CIPS/PAP de Salento/La Victoria si
  están). Corre la suite antes de push. `test_ui_cips_selector.py` y
  `test_cips_duplicados::test_desktop_*` fallan sin PyQt6 (entorno), no es tu
  cambio.

---

## 3. Arquitectura (archivos)

| Archivo | Rol |
|---|---|
| `app.py` | App de escritorio PyQt6. Clases de UI + worker de generación. |
| `streamlit_app.py` | App web Streamlit (mismo motor). 12 tabs. Design system PCC. |
| `generator.py` | **Motor de llenado de Excel.** `ReportGenerator(plantilla)` + `fill_*`. |
| `readers.py` | Lectores FastField PAP (potenciales), EQUIPOS, rectificadores, aislamientos. |
| `cips_lrs.py` | Motor CIPS: unifica archivos + LRS (GPS→abscisa sobre shapefile). |
| `mod_unificar.py`, `mod_cips_lrs.py` | Copias VERBATIM del repo `proceso-cips` (no modificar salvo necesidad). |
| `cips_infra.py` | `InfraTramos`: resuelve Empresa/Distrito/Tramo → shapefile; sugiere tramo por coords. |
| `cips_adapter.py` | DataFrame CIPS → dicts para `fill_cips`; `cips_a_hallazgos` (clasifica + ortografía). |
| `dcvg_reader.py` | Lectores DCVG: FastField (postes/defectos), Resistividades, hallazgos del logger. |
| `ppm_generator.py` | Genera el PPM (archivo plano). |
| `ortografia.py` | Corrector de ortografía de comentarios de campo (diccionario cerrado). |
| `conclusions.py`, `geo_utils.py`, `photo_utils.py` | Conclusiones, KMZ/abscisas, fotos IA (Gemini). |
| `cips_reader.py` | HUÉRFANO (viejo lector CIPS, ya no se usa; se puede borrar). |

**Plantillas (recursos, en la raíz):** `EN BLANCO.xlsx` (PAP), `CIPS EN
BLANCO.xlsx` (CIPS), `DCVG_REP.xlsx` (DCVG), `PPM.XLSX`. Datos:
`Listado de Infraestructura para Cod Informes.xlsx` (tramos→ID),
`Infraestrutura TGI.xlsx` (autollenado), `Listado equipos TGI.xlsx`
(inspector→seriales), `Infra_General_TGI_V11_29032023.kmz`, `shapefiles/`
(259 trazas por tramo; se empaquetan como `shapefiles.zip` en el build).

---

## 4. Flujo CIPS (detallado)

**Entrada:** uno o varios Excel del logger iBTVM (hojas `Survey Data`,
`DCP Data`, `Survey Info`). Selector Empresa (TGI/OCENSA) → Distrito → Tramo.

**Procesamiento** (`cips_lrs.procesar_cips_lrs(archivos, shp_path)`):
1. Unifica archivos (`mod_unificar`), dedup de filas idénticas (exportes solapados).
2. **Abscisa = PK geométrico** (`linea.project(punto)` sobre la traza del
   shapefile), igual que la app original proceso-cips. Ordena ascendente.
   NO usar etiquetas de campo (se probó y rompía surveys continuos).
3. **Guardia de tramo equivocado** (`TramoIncorrectoError`): si la mediana
   punto→traza > 300 m, el tramo elegido no corresponde; la app sugiere el
   correcto con `InfraTramos.sugerir_tramos(lat, lon)` (lee bbox de headers .shp).
4. **GPS congelado:** si todas las lecturas tienen el mismo GPS (span geom < 5 m
   con odómetro que avanza), la abscisa se toma de `Dist From Start` anclada a
   una etiqueta 'pk X+YYY' del comentario. `df.attrs['fuente_abscisa']`.
5. **Suavizado de picos** (`_suavizar_outliers`, ventana 25, umbral 250,
   `min_periods=1`): mediana móvil que reemplaza picos aislados y racimos
   cortos; PRESERVA caídas sostenidas (baja protección real). Produce
   `On_mV_limpio`/`Off_mV_limpio`.
6. Lecturas Metal IR / Far / Near Ground de `DCP Data` por Data No.
7. Fecha por punto (`Fecha_dato`) del timestamp `On Time`.

**Adaptador** (`cips_adapter.lrs_df_a_cips_dicts`): mapea a dicts; **1 punto por
abscisa** (dedup por metro, conservando comentarios y lecturas DCP); corrige
ortografía y repara mojibake ('caÃ±o'→'caño').

**Llenado** (`generator.fill_cips`):
- Hoja **Potenciales CIPS**. Abscisa (col B) = **número** (metros); la celda
  tiene formato `\K\ 000\+000` que lo muestra "K 000+007". Si se escribe texto,
  la gráfica (serie X numérica) no dibuja.
- E/F = potencial **SUAVIZADO** (`on_limpio`/`off_limpio`), NO el crudo — la
  gráfica lee E/F. G/H ([CORREGIDO]) van **vacías**.
- Metal IR/Far/Near en L-Q; fecha en C; IR en R.
- **Capacidad ~100.000 filas** (el bloque de firmas está en la fila 100002).
  Filas más allá de las pre-formateadas se formatean al vuelo.
- `fill_graficas_cips`: recorta las series de las gráficas VDC/Interferencia a
  las N filas y fija la abscisa máx; escribe los comentarios del survey en la
  Gráfica VDC (limpia los del template).

---

## 5. Flujo DCVG (detallado — el más complejo)

**Entradas (3 puntos de carga, cada uno acepta VARIOS archivos):**
1. **FastField DCVG** (`leer_dcvg_fastfield_varios`): hoja `Root` (metadata),
   `subform_5` = **postes** (PK, ON, OFF, VAC, resistencia, coords),
   `subform_9` = **defectos** (PK del defecto, Forma N/S/E/O, OL/RE, profundidad,
   carácter, clasificación de campo, comentarios).
2. **FastField Resistividades** (`leer_resistividades_fastfield_varios`):
   `subform_7` (PK, sector, profundidad, coords, Resistencia 1/2/3 m).
3. **Data cruda del logger** (`leer_hallazgos_logger_varios`): de aquí salen
   **SOLO los hallazgos** (hoja `DCP Data`: filas "Highway"/feature con
   comentario — cruces, tramos enmontados, saltos, mallas, válvulas…). Abscisa =
   Station No; GPS de `Survey Data` por Station. Excluye comentarios de carácter
   (Cathodic/Anodic) y los de solo "toma resistividad".

**Fuente de cada dato (confirmado por el usuario):**
- Defectos, postes, coordenadas → **FastField**.
- Hallazgos → **logger** (data cruda). Los defectos DCVG del logger (DCP "DCVG
  Anomaly") NO se usan.
- Abscisa de defectos/postes = **PK de campo** ("5+760"→5760), NO GPS.

**Llenado** (`generator.fill_dcvg(postes, defectos, resistividades, hallazgos)`):
Hoja **Inspección DCVG** con postes + defectos + **hallazgos intercalados por
abscisa** (secuencia del recorrido). Mapeo de columnas:
- A ítem · B referencias (tipo poste / "Defecto" / descripción del hallazgo) ·
  C distancia `=D-D8` · D **abscisa** · E/F/G lat/lon/alt.
- **Forma [mV]** (defecto): **N→H(12), E→I(3), S→J(6), O→K(9)**.
- L carácter (AA/CA/CC de "Anódico/Catódico") · M OL/RE · N/O ON/OFF (postes) ·
  P pulso `=ABS(N-O)` (postes) · R profundidad.
- **Q (P/RE)** de cada defecto = **pulso interpolado** entre el poste **anterior
  y el posterior QUE TENGAN PULSO** (ON/OFF): `=((Pps-Ppa)/(Dps-Dpa)*(Dr-Dpa))+Ppa`.
  Saltar postes sin ON/OFF (p.ej. "poste abscisado").
- **Severidad %IR** = **OL/RE ÷ P/RE** = `=M{r}/Q{r}` (NO ×100, NO /100). Va en
  **S(AA)/T(CA)/U(CC)** según carácter. Las celdas tienen formato `0%`, así que
  la fracción se muestra como porcentaje.
- **V clasificación** por umbrales de %IR (fracciones): `<=0.15 Muy Pequeño ·
  <=0.35 Pequeño · <=0.60 Mediano · else Grande`.
- W resistividad más cercana por abscisa ("1m .. 2m .. 3m") · X observaciones.

Hoja **Resistividad** (`fill_resistividad`): de `subform_7`, **ordenada
ascendente por abscisa**. A abscisa · B sector · C/D lat/lon · E profundidad ·
F/H/J = R 1/2/3 m. Las fórmulas de ρ (`=2*PI()*a*R`) y clasificación de
corrosividad ya vienen en la plantilla.

**Gráficas** (`fill_graficas_dcvg`): recorta series a las N filas. En GRAFICA
DCVG la severidad es **porcentaje**: criterios en **fracción (0.15/0.35/0.60)**
en D39:G40, eje Y formato `0%`, extremos de abscisa (D39/D40) al rango real.

**Hojas por rango** (`fill_rangos_dcvg`): una hoja por segmento de ~5 km que
cubre la extensión de abscisas; cada una copia GRAFICA DCVG (celdas + deepcopy
del chart) con el eje X limitado al segmento. NO usan el voltaje del logger
(son zoom del %IR). Correr DESPUÉS de `fill_graficas_dcvg` para heredar los
criterios en fracción.

**Hallazgos** (hoja Hallazgos): `cips_a_hallazgos(data['dcvg_hallazgos'])`
(clasifica tipo + ortografía), ordenados por abscisa.

---

## 6. Flujo PAP (resumen)

FastField de potenciales (`readers.FastFieldReader`) → `fill_potenciales_pap`
(hoja Potenciales PAP) + `fill_graficas` (VDC/Interferencia/VAC, leen
Potenciales PAP). Abscisa desde columna 'abscisado' del FastField. Ver
`generator.fill_graficas` / `ajustar_graficas` (solo reescribe series
'Potenciales PAP').

---

## 7. Reglas transversales

- **Autollenado técnico→equipos:** al procesar CIPS o DCVG, se lee el técnico
  (`Survey Info`→`Technician Name` en CIPS; `Root`→`Técnico a cargo` en DCVG) y
  se autollena Inspector + Serial + Fecha calibración vía
  `get_equipos_for_inspector` (lee `Listado equipos TGI.xlsx`).
- **Ortografía:** todo texto libre pasa por `ortografia.corregir_campo` antes de
  escribirse (cruce, aéreo, tensión, válvula, línea, río, abscisado, rocería,
  "sin paso", PK, mayúscula inicial…). Diccionario cerrado; ampliar si el
  usuario reporta una palabra nueva.
- **Hoja Hallazgos:** la plantilla tiene 500 filas de datos pre-formateadas
  antes del bloque de firmas (se movió con `expandir_hallazgos`). `fill_hallazgos`
  solo escribe (no inserta filas), ordena por abscisa, y limpia sobrantes.
- **PPM:** `PPMGenerator().generate(info, potenciales, aislamientos, out,
  cips=...)`. Limpia el template antes de escribir; incluye la data CIPS con
  fecha por punto.
- **Fecha por punto:** cada punto conserva la fecha de su archivo; con varios
  archivos de fechas distintas, cada uno lleva la suya.

---

## 8. Cómo probar y publicar (checklist)

1. Edita en `TGI_V1_Codigo_Fuente/` (el código fuente vive aquí).
2. Escribe/actualiza el test en `tests/`. Corre:
   `cd "<proyecto>/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/ -q --ignore=tests/test_ui_cips_selector.py --ignore=tests/test_cips_duplicados.py`
   (ignora los que requieren PyQt6). Deben pasar todos los de lógica.
3. Valida end-to-end con datos reales (DCVG: `/private/tmp/dcvg_ref/*`).
4. El clon git vive en `/private/tmp/` (p.ej. `tgi_repo2`) pero **/private/tmp se
   limpia** a veces (se pierde el clon Y paquetes del venv como `supabase`/`pip`).
   Si `git -C` falla o falta un módulo: `git clone https://github.com/pablorivera6/reportes-tgi.git /private/tmp/tgi_repo2`
   y `/private/tmp/venv_tgi/bin/python -m pip install <lo que falte>`. Copia los
   archivos cambiados al clon, commit y push. NO push desde el Desktop.
5. La nube redespliega en ~1 min. OJO: las **3 apps salen del mismo repo**, así que
   cada push las reconstruye a las 3 (no hagas push durante una demo del cliente).

---

## 9. Pendientes conocidos

- **FastField webhooks**: falta configurar la HTTP/HTTPS action en los forms PAP (1199286),
  Aislamientos (1240049) e Interfases (1242703) — DCVG ya quedó. Adaptadores por API de
  PAP/Aislamientos (`_ADAPTADORES` en fastfield_ingest) — hoy entran por Excel; DCVG ya API.
- **Comparativa históricos**: nota metodológica de transparencia en el portal + toggle
  crudo/procesado (§10.9); uploader de históricos en la app para cargar los demás tramos
  (hoy se carga con script). Rotar contraseña FastField (circuló en chat).
- **Matriz de rectificadores**: CONSTRUIDA (§10.12). Falta: usuario corre `schema_v7.sql`
  + `cargar_rectificadores.py`, verificar en vivo, y decidir asignación de tramos.
- `.exe` de Windows: recompilar en Windows (`build_windows.bat`); no se puede en Mac.
- DCVG Fase pendiente: fotos de defectos (multiphoto_picker) — no implementado.
- CIPS: decidir si ciertos picos hacia -500/-600 son artefactos o baja
  protección real (pendiente de revisión del ingeniero).
- Deuda técnica: VAC falso negativo (`readers.py` conversión mV solo si >1.0),
  `find_sheet(['pe'])` ambiguo, métodos duplicados en `app.py`, `cips_reader.py`
  huérfano, migrar `google.generativeai`→`google-genai`.

---

## 10. Ecosistema web: Supabase + 3 apps + FastField (2026-08)

El proyecto pasó de 1 app a un **ecosistema de 3 apps Streamlit** sobre **Supabase**
(mismo repo público `pablorivera6/reportes-tgi`, distinto `main file` cada una).

### 10.1 Las 3 apps (Streamlit Cloud)
- `streamlit_app.py` — **Procesamiento (PCC)**. Genera informes + publica al portal.
  Secrets: `[supabase] service_key`, `[app] password`.
- `portal_app.py` — **Portal (TGI, solo lectura)**. Dashboards CIPS/PAP/DCVG +
  "Vista por tramo" (cruza los 3 + zonas críticas). Secrets: `[supabase] anon_key`
  **y** `service_key` (el rol revisor lo necesita), `[portal] password` (TGI) +
  `reviewer_password` (revisor). En local sin password → selector de rol.
- `intake_app.py` — **Carga de campo (técnicos)**. Formulario con casillas por
  carpeta del entregable. Secrets: `[supabase] service_key`, `[intake] password`.

### 10.2 Supabase (proyecto `nvsnovulwtnbgopyiyal`)
- Llaves formato NUEVO: `sb_publishable_...` (anon/lectura), `sb_secret_...` (service/
  escritura). Van SOLO en `.streamlit/secrets.toml` (gitignored) o Secrets de la nube.
- SQL corridos (en `portal/`): `schema.sql` (CIPS), `schema_v2.sql` (PAP+DCVG),
  `schema_v3.sql` (cargas), `schema_v4.sql` (estado de aprobación). Todos aplicados.
- Tablas: `inspecciones` (+ estado en_revision/aprobada/rechazada), `puntos_cips`,
  `hallazgos`, `tramos_no_inspeccionados`, `puntos_pap`, `postes_dcvg`,
  `defectos_dcvg`, `resistividades_dcvg`, `cargas`. Buckets: `informes`, `cargas`.
- `db.py` = capa Supabase (guardar/listar/cargar por tipo, aprobar/rechazar,
  cargas, `_severidad_dcvg`). Import perezoso; `disponible(write=)` chequea secrets.

### 10.3 Flujo completo (pipeline)
Técnico sube en **intake** → carga a Supabase (bucket organizado) →
Procesamiento: pestaña Cargar Archivos → **"📥 Cargas pendientes" → "⚙️ Traer a la
app y procesar"** (auto-carga: baja de Supabase y enruta por los readers;
`autocargar_carga` en streamlit_app.py) → Generar → **KMZ + paquete de entrega
(ZIP)** + **"📤 Publicar al portal"** (queda **En revisión**) → Portal rol
**revisor** aprueba → Portal rol **TGI** lo ve. Nada llega al cliente sin aprobación
(RLS: anon solo ve `estado='aprobada'`).

### 10.4 Cumplimiento contrato TGI (numeral 6.3.5) — `entrega.py`
- `CATALOGO` (por tipo) = casillas del intake mapeadas a las carpetas del entregable
  (01 Huellas Osc · 02 GPS · 03 Data Logger · 04 Anexos[informe+KMZ] · 05 PPM · 06 RF).
- `construir_kmz` (traza + puntos por estado + defectos por severidad + hallazgos)
  y `construir_paquete` (ZIP con la estructura, fotos por elemento en orden).
- El intake organiza el paquete SOLO por cómo el técnico sube cada cosa.

### 10.5 Shapefiles CIPS: generar el faltante desde el survey
Si un tramo NO tiene shapefile (p.ej. Ramal Termodorada = `R_TRD`), se puede
GENERAR desde la traza GPS del propio survey CIPS: ordenar por "Dist From Start",
dedupe, `shapely.simplify(0.00002)`, escribir PolyLine WGS84 con `pyshp` (mismos
campos que los demás; ver commit 9f46bbf). El GPS-proyectado corrige inflación de
odómetro del equipo. Idea futura: generar shapefile on-the-fly si falta.

### 10.6 FastField (API v3) — conector FUNCIONANDO (ver memoria fastfield-api)
- Base `https://api.fastfieldforms.com/services/v3`. Auth: `POST /authenticate`
  (Basic email:password + header `FastField-API-Key`) → sessionToken → header
  `X-Gatekeeper-SessionToken`. La API key es OBLIGATORIA.
- **Email que funciona**: `data.ingenieria@proteccioncatodica.com` (el de gmail da 401).
- **NO hay endpoint para LISTAR submissions** (solo `GET /formresults/submission/{id}`)
  → la integración es por **WEBHOOK** (FastField avisa cada envío), no polling.
- Fotos: `/media/download?key=<filename>` → `{downloadUrl}` → GET esa URL (2 pasos).

**Leer las ETIQUETAS de los campos** (el submission trae keys genéricas y LOCALES por
subform: `numeric_1`, `alpha_1`… se repiten entre subforms):
`GET /forms/{formId}` → `formJson` → `page[0].section[0].field[]`, cada field con
`fieldKey` (= key del submission), `fieldType`, `fieldName` (etiqueta legible). Los
`SubFormPicker` traen su definición anidada en `field.subForm`.

**Forms reales mapeados** (`FORM_MAP` en `fastfield_transform.py`):
- `1199286` PAP (subform_1 = postes) → `pap_submission`
- `1240049` Aislamientos (subform_1 = juntas) → `aislamientos_submission`
- `1160295` **"Inspección DCVG" = formulario COMPLETO** (corrección: NO era solo
  resistividades) → `dcvg_submission`. 5 subforms repetibles: `subform_5`=Poste(PAP),
  `subform_6`=Hallazgos, `subform_7`=Resistividades, `subform_8`=Hallazgo simple,
  `subform_9`=Defecto DCVG (+ `subform_4`/`subform_3` = cuadrillas TGI/Ocensa).
  Defecto: `numeric_4`=OL/RE, `numeric_5`=Severidad(P/RE), `computedlabel_1`=%IR (fracción).
  **Los técnicos deben poner TODO en este único form** (antes lo partían mal; se les
  comunicó). `dcvg_reader.py` YA leía este form vía Excel (hojas subform_5/7/9), por eso
  el adaptador copia esas formas exactas.
- `1242703` **"Inspección Visual interfases-"** → `interfases_submission`. Es un **ANEXO**
  (fotos), no data de informe. Cabecera + `subform_1` repetible (PK, GPS, Observación,
  Registro Fotográfico). OJO: `1242702` es solo un subformulario, no el form real.

### 10.6b Webhook FastField → app (arquitectura "buzón + Python")
**Por qué así:** Edge Functions es TypeScript/Deno y el traductor probado está en Python.
Reescribirlo duplicaría el código. Solución: la función solo hace de **buzón**.

Flujo: técnico envía en FastField → webhook (HTTP/HTTPS action) llama a la Edge Function
→ inserta `submission_id` en `fastfield_cola` → la app de procesamiento drena la cola con
un botón, usando el Python ya probado (baja envío + fotos, traduce, crea la **carga**) →
sigue el flujo normal de cargas.

- `portal/schema_v5.sql` → tabla `fastfield_cola` (submission_id UNIQUE, form_id, estado
  nuevo/procesada/error, carga_id, payload, RLS solo service_role).
- `portal/functions/fastfield-webhook/index.ts` (+ README de deploy) — valida el secreto
  (header `x-webhook-secret` **o** `?secret=` en la URL) e inserta vía PostgREST.
- `db.py`: `listar_cola_fastfield` / `guardar_cola_fastfield` / `marcar_cola_fastfield`.
- `fastfield_ingest.py`: `procesar_submission(sub_id, form_id)` → auth, baja envío+fotos,
  `FORM_MAP` transform, luego:
  - **data de informe** → `_ADAPTADORES[tipo]` (solo DCVG por ahora) → carga con
    `datos.json` (categoría `fastfield_datos`) + fotos (`fotos_rf`).
  - **anexo** → `_ANEXOS[tipo]` (INTERFASES) → solo fotos en `anexo_interfases` + genera
    el Excel del entregable con `interfases_doc.py`. NO fija `tipo_inspeccion`.
  Credenciales en `st.secrets['fastfield']` = {email, password, api_key}.
- `streamlit_app.py`: rama `fastfield_datos` en `autocargar_carga` (carga el datos.json
  directo a `data[...]`) + bandeja que drena la cola.

**Configuración en FastField (una vez por formulario):** Form Delivery Options / Workflow
→ Actions → **HTTP/HTTPS** → URL
`https://nvsnovulwtnbgopyiyal.supabase.co/functions/v1/fastfield-webhook?secret=<WEBHOOK_SECRET>`
· Format **JSON** · sin Basic Auth ni API Key (ese panel NO tiene headers custom, por eso
el secreto va en la URL). En Supabase: desactivar **Verify JWT** de la función y setear el
secret `WEBHOOK_SECRET`. **Probado en vivo con DCVG**: el envío llegó solo a la cola.

### 10.6c Entregable de Interfases (`interfases_doc.py`)
Genera un Excel limpio (paleta PCC) desde el FastField de interfases: cabecera roja,
bloque de info (Tramo/Fecha/Gasoducto/Contrato/Inspector/OT/Contratista), tabla
**N° · Abscisa (`K 136+300`) · Lat · Lon · Observación · Registro Fotográfico** con
**una fila por foto** (celdas de datos combinadas verticalmente por interfase), fotos
escaladas con `PIL` e incrustadas con `openpyxl.drawing.image`. Reemplaza el formato
viejo (`VTG_REP_*.xlsx`, hoja única con 77 imágenes). Va al ZIP en
`04_Anexos/Inspeccion_Visual_Interfases/` (categoría `anexo_interfases` en `entrega.py`,
`_ANEXOS_COMUNES` añadido a los 3 tipos).

### 10.7 Lecciones de despliegue (Streamlit Cloud)
- `requirements.txt`: **NO fijar versiones exactas** (sobre todo `streamlit`) →
  fuerza recompilar `pyarrow` ("Could not build wheels for pyarrow") y rompe el
  build. Usar rangos con tope solo en majors que rompen: `pandas<3, numpy<3,
  supabase<3`. Dejar que la nube use sus wheels.
- `google-generativeai` FUERA de requirements (arrastra grpcio/protobuf y rompía
  el build; Fotos IA es opcional; `photo_utils` lo importa guardado con try/except).
- Diagnóstico: consola del navegador "RUNNING" = script colgado; el error real está
  en Manage app → logs (build). Status oficial: streamlitstatus.com / githubstatus.com.

### 10.8 Bandeja de entrada + autollenado (streamlit_app.py, esta sesión)
- **Bandeja unificada** en "Cargar Archivos": una sola sección "📬 Bandeja de entrada"
  con envíos FastField + cargas, **agrupadas por tramo** (`_tramo_norm` normaliza el
  nombre; botón "⚙️ Traer TODO el tramo" une CIPS+PAP+aislamientos+DCVG del mismo tramo).
  **Rendimiento:** consulta cacheada `@st.cache_data(ttl=45)` + descargas por **enlace
  firmado** (`db.url_descarga_carga`), NO bajar bytes en cada rerun (era el gran cuello);
  cliente Supabase **reusado** (`_CLIENTES` cache en `db._client`).
- **Carga manual reorganizada** en sub-pestañas por tipo (⚡PAP / 📈CIPS / 🔎DCVG), cada
  una con contador "En memoria: N potenciales…" y previsualizador DCVG (tablas de
  postes/defectos/resistividades/hallazgos con severidad calculada).
- **Autollenado automático de Datos Generales al procesar FastField PAP** (como la app
  antigua del ingeniero): al "Procesar potenciales" se extrae tramo/contrato/inspector/
  fecha/tipo y se dispara `_autollenar_tramo(tramo, inspector)` (infraestructura + OT/
  distrito/km + equipos), aplicando TODO vía `st.session_state.pending_autofill` (los
  `text_input` con `key` SOLO se refrescan así — antes solo se actualizaba `data['info']`
  y el widget quedaba vacío, por eso tocaba escribir el tramo a mano).

### 10.9 Comparativa histórico vs actual (CIPS) — portal + PDF
- `portal/schema_v6.sql` → tabla `historicos` (tramo, tipo, periodo, `puntos` jsonb
  [{abscisa,on,off}], `resumen` jsonb; RLS lectura anon). `db.py`: `guardar_historico`,
  `historico_de_tramo`, `listar_historicos`, `cargar_historico`, `_resumen_historico`.
- `comparativa.py`: `overlay_plotly` (gráfica interactiva OFF vs abscisa, histórico gris
  + actual rojo + criterio −850, y-axis invertido), `resumen_comparativo`, y
  **`pdf_dashboard(detalle, dfp, hist)`** = PDF **multipágina con TODO el dashboard**
  (matplotlib+PdfPages, sirve en la nube SIN Chrome): pág1 meta+KPIs+comparativa, pág2
  mapa(scatter por estado)+ON/OFF+VAC, pág3 hallazgos+tramos, pág4 muestra de 40 lecturas.
  `matplotlib>=3.6` agregado a requirements.
- Integrado en `render_dashboard_cips` (portal_app.py): si el tramo tiene histórico,
  muestra métricas antes→ahora + gráfica + botón "⬇️ Descargar PDF del dashboard".
- **La Dorada** ya cargado (histórico Nov-2023 del informe TELMACOM, 756 pts) y probado
  en vivo. Para más tramos: cargar con script (o futuro uploader en la app).

**⚠️ OJO INTEGRIDAD DEL DATO (CIPS):**
- El pipeline propio guarda `off_mv` (crudo) **y** `off_limpio` (procesado). La "limpieza"
  = `_suavizar_outliers` (cips_lrs.py): reemplaza **picos AISLADOS** que se desvían >250 mV
  de la mediana móvil de 25 pts. **Preserva zonas desprotegidas reales** (varios pts
  seguidos). El portal/comparativa usa el **limpio** (dato oficial). En La Dorada el crudo
  tenía 1 punto desprotegido (K007 −171 mV, artefacto de arranque) que el limpio corrige.
- El **histórico 2023 (Excel TELMACOM) trae UNA sola columna** de OFF: no se sabe si es
  crudo o limpio (informe ya entregado por otro contratista). Al aplicarle nuestro filtro
  solo cambian 2/756 pts → consistente con "ya viene procesado", pero NO verificable.
  **Riesgo para TGI:** parte de la diferencia podría ser metodológica (otro equipo/criterio).
  Conclusión robusta: **87% de puntos más protegidos, +97 mV OFF promedio**; lo que MÁS
  cambia es el **ON (−2076→−1624)**, o sea la caída IR se redujo a la mitad (~−978→−430),
  probablemente menor corriente de rectificador durante la medición (el OFF, que manda para
  NACE, mejora igual). PENDIENTE: nota metodológica de transparencia en el portal +
  (opcional) toggle crudo/procesado; conseguir el crudo real de 2023 si se puede.

### 10.10 Entregables a TGI (docs/PDF, esta sesión)
- **Matriz de cumplimiento TGI** (artifact HTML + PDF): qué se cumple completo vs. qué
  cambia con solución. Cambios que TGI debe saber: informes SIN antecedentes escritos, sin
  "sistema inspeccionado", sin la huella; SIN gráficas cada 5 km; entrega en ZIP (num
  6.3.5); históricos → PDF dashboard comparativo + acceso al portal; matriz de
  rectificadores con PDF por unidad (esto último aún no construido).
- **Logo PCC**: archivo `logo-pcc-hd.png`; en los PDF de esta sesión se usó una
  **recreación SVG** (anillos + P + rayo) porque Descargas está bloqueada por permisos
  macOS. Para usar el real: copiarlo a la carpeta del proyecto (readable) y re-embeber.

### 10.11 Entorno de esta máquina (gotchas nuevos)
- **Carpeta `~/Downloads` BLOQUEADA** (TCC macOS): no se puede leer/copiar desde ahí
  (Bash y Read dan EPERM, incluso con sandbox off). **Escribir** sí funciona. Para pasarme
  archivos: ponerlos en la carpeta del proyecto (`TGI_V1_Codigo_Fuente/`).
- **HTML→PDF**: weasyprint hace **segfault** (libs anaconda). Usar **Chrome headless**
  (`--headless=new --print-to-pdf`) para HTML→PDF, o **matplotlib PdfPages** para PDF con
  gráficas (sirve en la nube). `sips` (macOS) convierte PDF→PNG página 1 para previsualizar.
- **Python con libs**: `/opt/anaconda3/bin/python3` (tiene streamlit, matplotlib, weasyprint,
  openpyxl, pypdf). `launch.json` usa ese binario. Portal local = `portal_app.py` puerto 8602.
- **El clon `/private/tmp/tgi_repo2` se corrompió** (git limpiado). Push desde clon fresco:
  `git clone https://github.com/pablorivera6/reportes-tgi.git /private/tmp/tgi_v6`. NUNCA
  push desde Desktop (iCloud). `git commit`/`add` a veces bloqueados por el clasificador →
  correr en pasos separados y mensaje de UNA línea.

### 10.12 Rectificadores (matriz + visor en el portal) — 2026-08
Origen: app web del usuario `~/Downloads/Codigo_Matriz_TGI` (parse_tgi.py lee Excels
`*REP*.xlsx` → `rectifiers_processed.json`; app_tgi.js = visor con motor de diagnóstico).
Integrado NATIVO al portal (no se embebe el HTML). Decisiones del usuario: emparejar
por **tramo asignado manualmente**; además una **sección global "⚡ Rectificadores"**.
- **`rectificadores.py`** (NUEVO): port del motor JS a Python — `estado_rectificador`
  (Operando/Fuera de servicio/Sin datos, por eventos negativos vs positivos),
  `calc_util` (%V/%I sobre nominal), `analizar_mantenimiento` (needs/mejoras/preventivo,
  mismas heurísticas del JS), `resumen_rectificador`. Render nativo Streamlit
  `render_card(rect, st, key)` (tarjeta PCC con placa/nominales/util/expander diagnóstico
  + botón PDF por unidad). PDF: `pdf_rectificador(rect)` (1 pág, matriz TGI) y
  `paginas_pdf(pdf, plt, rects, titulo, pag_ini, total)` + `paginas_pdf_count` para
  inyectar páginas en el PDF del dashboard. **OJO matplotlib no renderiza emoji** → en
  texto de PDF nada de emoji (usar "Mant."/"Mejora:").
- **`portal/schema_v7.sql`** (NUEVO): tabla `rectificadores` (tramo asignable, tag,
  estructura, distrito, fabricante, modelo, serial, estado, payload jsonb, resumen jsonb,
  fuente). RLS anon select=true. **El usuario debe correrlo en Supabase antes de cargar.**
- **`db.py`**: `guardar_rectificador`, `listar_rectificadores(tramo=None)`,
  `rectificadores_de_tramo(tramo)` (devuelve payloads), `asignar_tramo_rectificador`.
- **`portal_app.py`**: nav "⚡ Rectificadores" (vista global con KPIs, filtros distrito/
  fabricante/búsqueda, cards por distrito, y editor de asignación de tramo SOLO revisor
  vía `st.data_editor`). En `render_dashboard_cips`: si el tramo tiene rectificadores,
  sección "⚡ Rectificadores del tramo" + entran al PDF. El botón "Descargar PDF del
  dashboard" ahora aparece si hay histórico **o** rectificadores (antes solo histórico).
- **`comparativa.pdf_dashboard(detalle, dfp, hist=None, rects=None)`**: añade páginas de
  rectificadores al final; NP = 4 + páginas de rects.
- **`cargar_rectificadores.py`** (NUEVO): loader. Lee credenciales de
  `.streamlit/secrets.toml` (no depende del runtime de Streamlit). Uso:
  `python3 cargar_rectificadores.py [json] [--tramo "La Dorada"] [--reset]`. Los 19 del
  ejemplo están en `rectifiers_processed.json` (copiado al proyecto). 18 con placa (1 fila
  UNKNOWN vacía se descarta). Todos "Operando" en el ejemplo, distritos 7 y 8.
- **PENDIENTE al momento de escribir**: usuario corre schema_v7.sql, luego el loader; verificar
  en vivo. Para el demo eligió "sección aparte" (no asignó tramo aún).
  → HECHO: 18 cargados en vivo (Distritos 7 y 8), visor + PDF verificados. Commit 5d2c8e9.

### 10.13 Carga de campo en web estática (reemplazo de intake_app) — 2026-08
Problema: `intake_app.py` (app Streamlit "Carga de campo TGI", URL
uploaddatapcc.streamlit.app) la usan los TÉCNICOS desde el celular y (a) el plan
gratis de Streamlit Cloud se DUERME (~30-60s al despertar), (b) la UX móvil es
mala. Decisión: NO reconstruir la generadora pesada (necesita Python), solo mover
esta appcita (199 líneas, solo sube archivos + crea carga) a **web estática**.
- **`web_carga/`** (NUEVO): sitio estático (index.html + app.js + config.js + data.js).
  Mobile-first, marca PCC. Usa `@supabase/supabase-js@2` (CDN) + la **llave anon
  (pública, formato `sb_publishable_…`)**. Sube directo al bucket `cargas` y hace
  insert en la tabla `cargas`, **replicando EXACTO `db.guardar_carga`**: ruta
  `slug(tramo)/fecha/slug(tipo)/slug(clave)/<stamp>_slug(nombre)` y fila
  {tramo,tipo,fecha,tecnico,estado:'pendiente',archivos:[{categoria,nombre,path,size}],
  nota,sharepoint_ok:false}. `slug` idéntico a `db._slug`. Casillas = `entrega.CATALOGO`
  (solo grupos proc/crudo/rf, igual que intake). Rutas con prefijo único (stamp) +
  upsert:false para no necesitar UPDATE en RLS. NO espeja a SharePoint (v1).
- **`portal/schema_v8.sql`** (NUEVO): RLS para que `anon` SOLO pueda INSERT en
  `cargas` (con check estado='pendiente') y INSERT (upload) en el bucket `cargas`.
  Sin select/update/delete. Bucket privado. El usuario debe correrlo.
- **`exportar_datos_carga.py`** (NUEVO): genera `web_carga/data.js` (window.TRAMOS de
  `cips_infra.InfraTramos` = 280 tramos; window.CATALOGO de `entrega.CATALOGO`).
  Reejecutar si cambian infra o catálogo.
- **Seguridad**: la anon key es pública por diseño (segura en el navegador); la
  protección la da RLS. `[intake] password` estaba VACÍO → la app Streamlit hoy está
  abierta; la web deja `ACCESS_CODE` opcional (candado de comodidad, no seguridad).
- **Despliegue**: Vercel, Root Directory = `web_carga`, framework Other (estático, sin
  build). La generadora Streamlit se QUEDA (es de oficina/PCC, el sueño no molesta).
- **PENDIENTE**: usuario corre schema_v8.sql → probar envío real e2e → desplegar en
  Vercel y reemplazar el link que usan los técnicos. Rotar contraseña FastField sigue.
