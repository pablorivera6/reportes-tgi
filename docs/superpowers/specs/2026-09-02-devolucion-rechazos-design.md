# Devolución de informes rechazados — del portal al generador (+ asistente Claude)

Fecha: 2026-09-02
Estado: aprobado por el usuario

## Problema

En el portal, el revisor rechaza un informe con un texto libre
(`portal_app.py:329` → `db.rechazar_inspeccion`). A partir de ahí no pasa nada:
el único camino de vuelta es "↩️ Reabrir para revisión" (`portal_app.py:338`),
que solo cambia el estado y **borra la nota**. La app de procesamiento publica y
se olvida (`streamlit_app.py:1566`): guarda `publicado_id` en session_state y
nunca vuelve a consultar el estado.

Consecuencia: para corregir, el ingeniero vuelve a buscar la carga a mano,
re-sube los crudos y re-teclea Datos Generales. **Lo caro no es escribir la
corrección, es volver a montar el escenario.**

## Causas reales de rechazo (confirmadas con el usuario — las cuatro aplican)

| Categoría | Qué se rompió | Dónde se arregla |
|---|---|---|
| `datos_generales` | Tramo, OT, contrato, inspector, fecha, ciclo | Editar campos + regenerar |
| `procesamiento` | Abscisa corrida, shapefile equivocado, picos, clasificación | Reprocesar los crudos |
| `texto_campo` | Comentarios, hallazgos mal redactados, conclusiones | Editar texto fila a fila |
| `falta_info` | Faltan fotos, resistividades, un archivo | **No vuelve al generador: vuelve al técnico** |

## Decisiones

- **Todo el arreglo vive en el generador.** El portal solo marca qué está mal.
  No se duplica lógica de generación en dos apps.
- **La rehidratación no depende de los crudos.** Las filas procesadas ya están
  en Supabase (`puntos_cips`, `puntos_pap`, `postes_dcvg`, `defectos_dcvg`,
  `resistividades_dcvg`, `hallazgos`) y `db.cargar_inspeccion_cips/pap/dcvg`
  (`db.py:279,510,520`) ya las leen. Eso cubre `datos_generales` y `texto_campo`
  incluso para informes que se generaron con carga manual (sin `carga_id`).
- **Claude propone, el ingeniero firma.** La IA no escribe el Excel ni republica.
- **La IA nunca es requisito.** Sin API key todo el flujo funciona a mano.

## Arquitectura

```
PORTAL (revisor)                     SUPABASE                 GENERADOR (PCC)
  Rechazar                                                      Bandeja de entrada
    ├ nota en lenguaje natural                                    └ 🔧 Rechazos por corregir
    ├ [Analizar] → ia_revision      observaciones_revision  ──────→  observaciones
    │   estructurar_nota()          (N filas por rechazo)           ├ Abrir para corregir
    └ revisor ajusta en data_editor                                 │   rehidrata de las tablas
                                    inspecciones                    │   + contexto.info
                                      carga_id, contexto,           ├ Reprocesar desde crudos
                                      revision                      │   (solo si hay carga_id)
                                                                    └ [Sugerir arreglos]
                                                                        proponer_correcciones()
                                                                        → diff aprobable
                                                                    Republicar → Rev.B
```

## 1 · Modelo de datos — `portal/schema_v9.sql` (nuevo)

```sql
alter table inspecciones add column if not exists carga_id uuid references cargas(id);
alter table inspecciones add column if not exists contexto jsonb;   -- info completo + params
alter table inspecciones add column if not exists revision text default 'A';

create table if not exists observaciones_revision (
    id            bigserial primary key,
    inspeccion_id uuid references inspecciones(id) on delete cascade,
    categoria     text not null,   -- datos_generales|procesamiento|texto_campo|falta_info
    campo         text,            -- 'info.tramo', 'hallazgo.descripcion', ...
    abscisa_ini   integer, abscisa_fin integer,
    nota          text,
    origen        text default 'revisor',   -- revisor | ia
    estado        text default 'abierta',   -- abierta | resuelta | descartada
    creado_en     timestamptz not null default now()
);
create index if not exists idx_obs_insp on observaciones_revision(inspeccion_id, estado);
alter table observaciones_revision enable row level security;
-- sin políticas para anon: solo service_role (revisor + generador)
```

`nota_revision` se conserva como resumen legible para no romper lo que el portal
ya muestra. `contexto` es pequeño: `info` completo + empresa/distrito/shapefile
elegido + `fuente_abscisa` + tipo publicado. **No** el dataset.

## 2 · Portal — rechazo estructurado

El popover de `portal_app.py:329` pasa de `text_input` a:

1. `text_area` donde el revisor escribe como habla.
2. Botón **Analizar** → `ia_revision.estructurar_nota(nota, contexto)` devuelve
   las observaciones clasificadas a un `st.data_editor` que el revisor corrige,
   borra o amplía.
3. Sin API key, o si la llamada falla: formulario manual (categoría + abscisa +
   nota). El botón de rechazar nunca queda bloqueado por la IA.

`db.rechazar_inspeccion` acepta `observaciones: list[dict]` y las inserta.

## 3 · Generador — buzón y rehidratación

Sección **"🔧 Rechazos por corregir"** en la Bandeja de entrada
(`streamlit_app.py:701`), junto a cargas y FastField, con el mismo patrón de
caché (`@st.cache_data(ttl=45)`). Por cada rechazo, sus observaciones y:

- **Abrir para corregir** (siempre) — `revision.rehidratar(insp_id)` reconstruye
  `data` desde las tablas hijas y manda `contexto['info']` por
  `st.session_state.pending_autofill` (el mecanismo de `streamlit_app.py:306`;
  los `text_input` con `key` solo se refrescan así).
- **Reprocesar desde crudos** (solo si hay `carga_id`) — reusa
  `autocargar_carga` (`streamlit_app.py:399`) con la carga original. Único
  camino válido para `procesamiento`.

Fija `st.session_state.corrigiendo = {"id": insp_id, "revision": "A"}`.

### Mapeador inverso (la pieza delicada)

La BD y el generador nombran distinto los mismos campos:

| Tabla | Generador |
|---|---|
| `abscisa` | `abscisa_val` |
| `lejano_on` / `lejano_off` | `far_on` / `far_off` |
| `cercano_on` / `cercano_off` | `near_on` / `near_off` |
| `observaciones` | `observaciones` / `referencia` |
| `defectos_dcvg.severidad_pct` (%) | **no se rehidrata** — `_severidad_dcvg` lo recalcula |

Los campos **derivados** (`p_re`, `severidad_pct`, `clasificacion`, `estado`) no
se rehidratan: `db._severidad_dcvg` y `dashboard.estado_cp` los vuelven a
calcular al publicar. Eso elimina de raíz el riesgo del `%` vs. fracción y
refuerza que la IA no puede tocarlos.

Va en `revision.py`, con **test de ida y vuelta por tipo** (dict → `guardar_*`
→ `cargar_*` → `rehidratar` → dict). Si esto se desincroniza, el informe
corregido sale mal y nadie se entera: es el test que no puede faltar.

## 4 · Claude — contrato exacto

`ia_revision.py`, sin Streamlit adentro, sobre `claude-opus-5` (constante
`MODELO` del módulo; bajarlo a `claude-sonnet-5` para recortar costo es un
cambio de una línea, pero esa decisión es del usuario, no del diseño):

```python
estructurar_nota(nota: str, contexto: dict) -> list[Observacion]
proponer_correcciones(obs, contexto, filas) -> list[Cambio]
#   Cambio = {ruta, valor_antes, valor_despues, razon}
```

Tres barreras, **las tres en código, no en el prompt**:

1. **Lista blanca de rutas.** Solo `info.*` y campos de texto (`observaciones`,
   `descripcion`, `tipo` de hallazgo). Todo `Cambio` que apunte a `on_mv`,
   `off_mv`, `abscisa`, `severidad_pct`, `ol_re`, `p_re` o `clasificacion` se
   **descarta antes de mostrarse**. Validador, no confianza: es dato de medición
   bajo contrato; si la IA lo "arregla", el informe deja de ser defendible.
2. **Contexto acotado.** Solo las filas de las abscisas que señalan las
   observaciones, nunca las 100.000.
3. **Nada se aplica solo.** Los cambios llegan a un `data_editor` con casilla
   "aplicar"; el ingeniero marca y confirma.

`anthropic` entra a `requirements.txt` con el patrón de `google-generativeai`:
import guardado en try/except, ausencia manejada sin fallar. Credencial en
`st.secrets['anthropic']['api_key']`.

## 5 · Revisiones

`nombres.nombre_archivo(info, doc, ext, revision="A")` — parámetro nuevo con
default, en vez del `"Rev.A"` quemado de `nombres.py:198`. No rompe llamadas
existentes.

Al republicar una corrección la inspección **se actualiza en sitio**: vuelve a
`en_revision`, `revision` sube a la siguiente letra, las observaciones pasan a
`resuelta`. El portal no acumula duplicados y el Excel de la Rev.A se conserva
en el bucket.

Concretamente: hoy `guardar_inspeccion_*` siempre hace `insert`. Con
`st.session_state.corrigiendo` fijado, en vez de insertar debe **actualizar la
fila existente y reemplazar las filas hijas** (borrar las de esa inspección y
re-insertarlas). Se implementa como un parámetro `reemplaza_id: str | None = None`
en las tres funciones, no como una función paralela.

## 6 · Falta de información

`falta_info` no abre el buzón: arma el texto listo para copiar con lo que falta
y marca la carga como `incompleta`. **No hay canal hacia el técnico** (la web de
carga es de una vía) y se documenta como tal en vez de fingir una notificación.

## Archivos

| Archivo | Cambio |
|---|---|
| `portal/schema_v9.sql` | **nuevo** — columnas + `observaciones_revision` |
| `revision.py` | **nuevo** — modelo de observación, mapeador inverso, `rehidratar` |
| `ia_revision.py` | **nuevo** — cliente Claude + validador de lista blanca |
| `db.py` | `carga_id`/`contexto` en `guardar_inspeccion_*`; `guardar_observaciones`, `observaciones_de`, `listar_rechazadas`, `marcar_corregida` |
| `portal_app.py` | rechazo estructurado en `_barra_revision` |
| `streamlit_app.py` | buzón de rechazos; `carga_id` al autocargar; diff aprobable; republicar como revisión |
| `nombres.py` | parámetro `revision` |

## Pruebas

- Round-trip por tipo (CIPS/PAP/DCVG) del mapeador inverso — **el crítico**.
- Validador de lista blanca con respuestas mock de Claude, **sin llamar la API**:
  un `Cambio` sobre `off_mv` debe descartarse.
- `nombre_archivo` con `revision="B"`.
- Observaciones: guardar N, leerlas, marcarlas resueltas.

Suite: `/private/tmp/venv_tgi/bin/python -m pytest tests/ -q
--ignore=tests/test_ui_cips_selector.py --ignore=tests/test_cips_duplicados.py`

## Fases

- **Fase 1** — todo menos la IA. Funciona sola; es donde está el ahorro de tiempo.
- **Fase 2** — `ia_revision.py` y sus dos puntos de entrada.

Las notas de rechazo reales que se acumulen en la fase 1 son el material con el
que se afina el prompt de la fase 2. Meter la IA primero sería promptear a ciegas.

## Fuera de alcance

- Notificación al técnico (no hay canal).
- Que la IA edite datos de medición.
- Agente que corrija y republique sin humano.
