# Portal TGI — Persistencia y visualización de inspecciones

Fecha: 2026-08-03
Estado: aprobado por el usuario

## Problema

Hoy la app de reportes guarda todo en `st.session_state` (efímero): al recargar,
cerrar pestaña o reiniciar el servidor se pierde la data. TGI necesita entrar en
cualquier momento y ver el histórico de inspecciones ya procesadas.

## Decisiones (confirmadas con el usuario)

- **Dos apps separadas**: la de procesamiento (PCC) **migra** la data a Supabase;
  una **app portal** (TGI) la lee y muestra el dashboard. URLs y despliegues
  independientes.
- **Backend**: Supabase (Postgres + Storage + Auth), plan gratis.
- **Roles**: PCC guarda/publica; TGI solo lee.
- **Alcance inicial**: CIPS. Luego DCVG y PAP.
- **Dashboard anclado al informe CIPS original** (nada decorativo).
- **UI**: reutilizar el design system PCC ya existente (rojo #C7113A, Calibri,
  logo, "fits you_", footer "For Internal Use Only").

## Arquitectura

```
APP A — Procesamiento (PCC, streamlit_app.py existente)
  Cargar archivos → procesa CIPS → [📤 Publicar al portal] → Supabase (escribe)

Supabase
  Postgres: inspecciones, puntos_cips, hallazgos, tramos_no_inspeccionados
  Storage:  bucket 'informes' (Excel/PPM generado)
  RLS:      PCC (service_role) inserta; TGI (anon+login) solo SELECT

APP B — Portal (TGI, portal_app.py nuevo)
  Login TGI → lista de inspecciones (tramo·fecha·tipo) → Dashboard CIPS (lee)
```

## Contenido del dashboard CIPS (mapeo al informe)

Cada sección corresponde a algo que el informe ya pide:

1. **Encabezado**: Gasoducto, Tramo, Fecha, Inspector, Tipo, Ciclo, OT
   (hoja *Informe*).
2. **KPIs de cumplimiento**: % puntos ≤ −850 mV (mismo criterio del COUNTIF del
   informe), total lecturas, longitud inspeccionada (abscisa MIN→MAX),
   # hallazgos, # tramos no inspeccionados.
3. **Gráfica de potenciales (VDC)**: ON/OFF vs abscisa con línea −850 mV
   (réplica de *Gráfica VDC*).
4. **Gráfica VAC**: VAC vs abscisa, criterio 15 VAC (réplica de *Gráfica VAC*;
   solo si hay data VAC).
5. **Mapa georreferenciado**: traza coloreada por estado (usa lat/lon de la data).
6. **Tabla de potenciales**: columnas de *Potenciales CIPS*.
7. **Tabla de hallazgos**: columnas de la hoja *Hallazgos*.
8. **Tramos no inspeccionados**: hoja *Inv. Tramos no Inspeccionados*.

Estado por punto (criterio NACE SP0169 sobre Instant-OFF):
- OFF ≤ −1200 mV → Sobreprotegido
- −1200 < OFF ≤ −850 → Protegido
- OFF > −850 mV → Desprotegido

## Modelo de datos (CIPS)

`inspecciones`
- id (uuid, pk), tipo (text: 'CIPS'|'DCVG'|'PAP'), gasoducto, tramo, fecha (date),
  inspector, ciclo, ot, contratista, serial_equipo, tipo_recubrimiento, diametro,
  abscisa_ini (int), abscisa_fin (int), resumen (jsonb: KPIs), excel_path (text),
  ppm_path (text), creado_por (text), creado_en (timestamptz default now())

`puntos_cips`
- id (bigserial, pk), inspeccion_id (uuid fk), item (int), abscisa (int),
  fecha (date), on_mv, off_mv, on_limpio, off_limpio, natural_mv, polarizacion_mv,
  vac_mv, metal_on, metal_off, lejano_on, lejano_off, cercano_on, cercano_off,
  ir_on_off, lat, lon, observaciones, estado (text)

`hallazgos`
- id (bigserial, pk), inspeccion_id (uuid fk), item (int), abscisa_ini (int),
  abscisa_fin (int), longitud_m, lat_ini, lon_ini, lat_fin, lon_fin, fecha (date),
  tipo (text), descripcion (text)

`tramos_no_inspeccionados`
- id (bigserial, pk), inspeccion_id (uuid fk), item (int), abscisa_ini (int),
  abscisa_fin (int), longitud_m, lat_ini, lon_ini, lat_fin, lon_fin, fecha (date),
  justificacion (text)

RLS: SELECT público (o por login TGI) en las 4 tablas; INSERT/UPDATE/DELETE solo
service_role (lo usa la App A al publicar).

## Componentes nuevos

- `db.py` — cliente Supabase y funciones:
  `guardar_inspeccion_cips(info, cips, hallazgos, tramos, excel_bytes, ppm_bytes)`,
  `listar_inspecciones(tipo=None)`, `cargar_inspeccion_cips(id)`.
- App A: botón **📤 Publicar al portal** en la pestaña Generar (o nueva pestaña),
  y retiro de la pestaña Dashboard (se muda al portal).
- App B: `portal_app.py` — login TGI, lista de inspecciones, dashboard CIPS.
- Reutiliza `dashboard.py` (`resumen_cips`, `estado_cp`) para los KPIs/estado.

## Secrets

- App A: `[supabase] url`, `service_key`. `[app] password` (PCC).
- App B: `[supabase] url`, `anon_key`. `[portal] password` (TGI) o Supabase Auth.

## Fuera de alcance (por ahora)

- DCVG y PAP en el portal (siguiente iteración; el esquema ya deja `tipo`).
- Fotos IA en el portal.
- Envío automático (webhook FastField) — iteración posterior.
