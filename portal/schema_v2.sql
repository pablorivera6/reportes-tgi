-- ============================================================================
-- Portal TGI — Esquema v2: PAP + DCVG  ·  PCC Integrity
-- Pegar en: Supabase → SQL Editor → New query → Run
-- Idempotente (create table if not exists). La tabla `inspecciones` y `hallazgos`
-- ya existen del schema.sql y se reutilizan (columna `tipo` = 'PAP' | 'DCVG').
-- ============================================================================

-- ── PAP: potenciales poste a poste (hoja "Potenciales PAP") ─────────────────
create table if not exists puntos_pap (
    id             bigserial primary key,
    inspeccion_id  uuid not null references inspecciones(id) on delete cascade,
    item           integer,
    abscisa        integer,
    fecha          date,
    on_mv          double precision,
    off_mv         double precision,
    natural_mv     double precision,
    polarizacion_mv double precision,
    vac_mv         double precision,
    ir_on_off      double precision,
    resistencia    double precision,
    lat            double precision,
    lon            double precision,
    ref_geografica text,
    observaciones  text,
    estado         text                       -- Protegido | Desprotegido | ...
);
create index if not exists idx_pap_insp on puntos_pap(inspeccion_id);
create index if not exists idx_pap_absc on puntos_pap(inspeccion_id, abscisa);

-- ── DCVG: postes (potencial de estructura, subform_5) ───────────────────────
create table if not exists postes_dcvg (
    id             bigserial primary key,
    inspeccion_id  uuid not null references inspecciones(id) on delete cascade,
    item           integer,
    abscisa        integer,
    tipo           text,
    on_mv          double precision,
    off_mv         double precision,
    vac_mv         double precision,
    resistencia    double precision,
    lat            double precision,
    lon            double precision
);
create index if not exists idx_postes_insp on postes_dcvg(inspeccion_id);

-- ── DCVG: defectos (subform_9) con severidad calculada ──────────────────────
create table if not exists defectos_dcvg (
    id             bigserial primary key,
    inspeccion_id  uuid not null references inspecciones(id) on delete cascade,
    item           integer,
    abscisa        integer,
    sector         text,
    forma_n        double precision,
    forma_e        double precision,
    forma_s        double precision,
    forma_o        double precision,
    caracter       text,                      -- AA | CA | CC
    ol_re          double precision,          -- gradiente OL/RE (mV)
    p_re           double precision,          -- pulso P/RE interpolado
    severidad_pct  double precision,          -- %IR = OL/RE ÷ P/RE * 100
    clasificacion  text,                      -- Muy Pequeño | Pequeño | Mediano | Grande
    profundidad    double precision,
    posicion_reloj text,
    lat            double precision,
    lon            double precision,
    comentarios    text
);
create index if not exists idx_defectos_insp on defectos_dcvg(inspeccion_id);
create index if not exists idx_defectos_absc on defectos_dcvg(inspeccion_id, abscisa);

-- ── DCVG: resistividades del suelo (Wenner 1/2/3 m) ─────────────────────────
create table if not exists resistividades_dcvg (
    id             bigserial primary key,
    inspeccion_id  uuid not null references inspecciones(id) on delete cascade,
    item           integer,
    abscisa        integer,
    sector         text,
    profundidad    double precision,
    r1             double precision,
    r2             double precision,
    r3             double precision,
    lat            double precision,
    lon            double precision
);
create index if not exists idx_resist_insp on resistividades_dcvg(inspeccion_id);

-- ── RLS: TGI (anon) solo lee; PCC escribe con service_role (omite RLS) ───────
alter table puntos_pap          enable row level security;
alter table postes_dcvg         enable row level security;
alter table defectos_dcvg       enable row level security;
alter table resistividades_dcvg enable row level security;

create policy "lectura portal pap"    on puntos_pap
    for select to anon, authenticated using (true);
create policy "lectura portal postes" on postes_dcvg
    for select to anon, authenticated using (true);
create policy "lectura portal defectos" on defectos_dcvg
    for select to anon, authenticated using (true);
create policy "lectura portal resist" on resistividades_dcvg
    for select to anon, authenticated using (true);
