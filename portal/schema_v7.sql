-- ============================================================================
-- Portal TGI — Esquema v7: Rectificadores (matriz + visor por tramo)
-- Pegar en: Supabase → SQL Editor → New query → Run  (idempotente)
-- ============================================================================
-- Guarda cada rectificador inspeccionado (placa, datos nominales y datos de
-- operación) con su estado calculado. El portal lo muestra en la sección
-- "⚡ Rectificadores" y, cuando un rectificador tiene un `tramo` asignado, lo
-- superpone en el dashboard de ese tramo y lo incluye en el PDF descargable.

create table if not exists rectificadores (
    id          uuid primary key default gen_random_uuid(),
    tramo       text,                               -- tramo del portal (asignable, puede ser NULL)
    tag         text,                               -- nombre/ubicación del rectificador
    estructura  text,                               -- "TRAMO / RAMAL" del archivo origen
    distrito    text,                               -- p.ej. 'DISTRITO 7'
    fabricante  text,
    modelo      text,
    serial      text,
    estado      text,                               -- ok | err | warn (calculado)
    payload     jsonb,                              -- {placa, nominales, op_data, obs, ...}
    resumen     jsonb,                              -- {estado, util, n_op, n_eventos}
    fuente      text,                               -- nombre del archivo origen
    creado_en   timestamptz not null default now()
);
create index if not exists idx_rect_tramo    on rectificadores (lower(coalesce(tramo, '')));
create index if not exists idx_rect_distrito on rectificadores (distrito, creado_en desc);

-- ── Seguridad ───────────────────────────────────────────────────────────────
alter table rectificadores enable row level security;

-- El portal (anon) puede LEER; la escritura queda para la app de procesamiento
-- (service_role, omite RLS).
drop policy if exists "lectura portal rectificadores" on rectificadores;
create policy "lectura portal rectificadores" on rectificadores
    for select to anon, authenticated using (true);
