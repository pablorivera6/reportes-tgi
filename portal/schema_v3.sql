-- ============================================================================
-- Portal TGI — Esquema v3: Cargas de campo (formulario de técnicos)
-- Pegar en: Supabase → SQL Editor → New query → Run  (idempotente)
-- ============================================================================

-- Una fila por envío del formulario de carga. Los archivos van a Storage
-- (bucket 'cargas') y aquí se guarda el índice organizado.
create table if not exists cargas (
    id            uuid primary key default gen_random_uuid(),
    tramo         text,
    tipo          text,                       -- CIPS | PAP | DCVG
    fecha         date,
    tecnico       text,
    estado        text not null default 'pendiente',  -- pendiente | procesada
    archivos      jsonb,                       -- [{categoria, nombre, path, size}]
    sharepoint_ok boolean default false,       -- se copió a SharePoint
    nota          text,
    creado_en     timestamptz not null default now(),
    procesada_en  timestamptz
);
create index if not exists idx_cargas_estado on cargas(estado, creado_en desc);

-- ── Bucket privado para los archivos crudos que suben los técnicos ──────────
insert into storage.buckets (id, name, public)
values ('cargas', 'cargas', false)
on conflict (id) do nothing;

-- ── Seguridad ───────────────────────────────────────────────────────────────
-- Solo la app de técnicos y la de procesamiento (service_role, omite RLS)
-- acceden a las cargas. El portal (anon) NO debe verlas: habilitamos RLS y NO
-- creamos políticas para anon -> anon queda sin acceso.
alter table cargas enable row level security;
