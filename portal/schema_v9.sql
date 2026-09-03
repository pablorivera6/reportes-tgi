-- ============================================================================
-- Portal TGI — Esquema v9: Devolución de informes rechazados
-- Pegar en: Supabase → SQL Editor → New query → Run  (idempotente)
--
-- Un rechazo deja de ser un párrafo y pasa a ser N observaciones con categoría
-- y ubicación. La inspección recuerda de dónde salió (carga_id) y con qué se
-- generó (contexto), que es lo que permite reabrirla en el generador.
-- ============================================================================

alter table inspecciones add column if not exists carga_id uuid references cargas(id);
alter table inspecciones add column if not exists contexto jsonb;
alter table inspecciones add column if not exists revision text not null default 'A';

create table if not exists observaciones_revision (
    id            bigserial primary key,
    inspeccion_id uuid not null references inspecciones(id) on delete cascade,
    categoria     text not null,   -- datos_generales|procesamiento|texto_campo|falta_info
    campo         text,            -- 'info.tramo', 'hallazgo.descripcion', ...
    abscisa_ini   integer,
    abscisa_fin   integer,
    nota          text,
    origen        text not null default 'revisor',   -- revisor | ia
    estado        text not null default 'abierta',   -- abierta | resuelta | descartada
    creado_en     timestamptz not null default now()
);
create index if not exists idx_obs_insp on observaciones_revision(inspeccion_id, estado);
create index if not exists idx_insp_rechazadas on inspecciones(estado, creado_en desc)
    where estado = 'rechazada';

-- Solo service_role (revisor + generador). El cliente TGI (anon) no ve rechazos.
alter table observaciones_revision enable row level security;
