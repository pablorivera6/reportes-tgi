-- ============================================================================
-- Portal TGI — Esquema Supabase (CIPS)  ·  PCC Integrity
-- Pegar en: Supabase → SQL Editor → New query → Run
-- ============================================================================

-- ── Tabla principal: una fila por inspección publicada ──────────────────────
create table if not exists inspecciones (
    id                 uuid primary key default gen_random_uuid(),
    tipo               text not null default 'CIPS',      -- CIPS | DCVG | PAP
    gasoducto          text,
    tramo              text,
    fecha              date,
    inspector          text,
    ciclo              text,
    ot                 text,
    contratista        text,
    serial_equipo      text,
    tipo_recubrimiento text,
    diametro           text,
    abscisa_ini        integer,
    abscisa_fin        integer,
    resumen            jsonb,                             -- KPIs (ver db.py)
    excel_path         text,                              -- ruta en Storage
    ppm_path           text,
    creado_por         text,
    creado_en          timestamptz not null default now()
);

-- ── Lecturas de potencial (hoja "Potenciales CIPS") ─────────────────────────
create table if not exists puntos_cips (
    id             bigserial primary key,
    inspeccion_id  uuid not null references inspecciones(id) on delete cascade,
    item           integer,
    abscisa        integer,
    fecha          date,
    on_mv          double precision,
    off_mv         double precision,
    on_limpio      double precision,
    off_limpio     double precision,
    natural_mv     double precision,
    polarizacion_mv double precision,
    vac_mv         double precision,
    metal_on       double precision,
    metal_off      double precision,
    lejano_on      double precision,
    lejano_off     double precision,
    cercano_on     double precision,
    cercano_off    double precision,
    ir_on_off      double precision,
    lat            double precision,
    lon            double precision,
    observaciones  text,
    estado         text                                   -- Protegido | ...
);
create index if not exists idx_puntos_insp on puntos_cips(inspeccion_id);
create index if not exists idx_puntos_absc on puntos_cips(inspeccion_id, abscisa);

-- ── Hallazgos (hoja "Hallazgos") ────────────────────────────────────────────
create table if not exists hallazgos (
    id             bigserial primary key,
    inspeccion_id  uuid not null references inspecciones(id) on delete cascade,
    item           integer,
    abscisa_ini    integer,
    abscisa_fin    integer,
    longitud_m     double precision,
    lat_ini        double precision,
    lon_ini        double precision,
    lat_fin        double precision,
    lon_fin        double precision,
    fecha          date,
    tipo           text,
    descripcion    text
);
create index if not exists idx_hall_insp on hallazgos(inspeccion_id);

-- ── Tramos no inspeccionados (hoja "Inv. Tramos no Inspeccionados") ──────────
create table if not exists tramos_no_inspeccionados (
    id             bigserial primary key,
    inspeccion_id  uuid not null references inspecciones(id) on delete cascade,
    item           integer,
    abscisa_ini    integer,
    abscisa_fin    integer,
    longitud_m     double precision,
    lat_ini        double precision,
    lon_ini        double precision,
    lat_fin        double precision,
    lon_fin        double precision,
    fecha          date,
    justificacion  text
);
create index if not exists idx_tramos_insp on tramos_no_inspeccionados(inspeccion_id);

-- ============================================================================
-- Seguridad (RLS): TGI (anon) solo LEE; PCC escribe con la service_role key,
-- que por diseño OMITE RLS (bypassa las políticas). Por eso solo definimos
-- políticas de SELECT para anon/authenticated.
-- ============================================================================
alter table inspecciones               enable row level security;
alter table puntos_cips                 enable row level security;
alter table hallazgos                   enable row level security;
alter table tramos_no_inspeccionados    enable row level security;

-- SELECT para clientes del portal (anon key). Si luego usas Supabase Auth,
-- cambia 'anon, authenticated' por 'authenticated'.
create policy "lectura portal inspecciones" on inspecciones
    for select to anon, authenticated using (true);
create policy "lectura portal puntos" on puntos_cips
    for select to anon, authenticated using (true);
create policy "lectura portal hallazgos" on hallazgos
    for select to anon, authenticated using (true);
create policy "lectura portal tramos" on tramos_no_inspeccionados
    for select to anon, authenticated using (true);

-- ============================================================================
-- Storage: bucket privado para los informes generados (Excel/PPM).
-- Ejecutar también, o crear el bucket 'informes' desde Storage (Private).
-- ============================================================================
insert into storage.buckets (id, name, public)
values ('informes', 'informes', false)
on conflict (id) do nothing;

-- Lectura de archivos del bucket para el portal (anon). La escritura la hace
-- la service_role (omite RLS).
create policy "lectura informes" on storage.objects
    for select to anon, authenticated using (bucket_id = 'informes');
