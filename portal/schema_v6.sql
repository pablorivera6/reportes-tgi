-- ============================================================================
-- Portal TGI — Esquema v6: Históricos por tramo (para la comparativa)
-- Pegar en: Supabase → SQL Editor → New query → Run  (idempotente)
-- ============================================================================
-- Guarda el perfil histórico de una inspección anterior por tramo (CIPS: perfil
-- ON/OFF vs abscisado). El portal lo superpone contra la inspección actual y
-- ofrece el PDF comparativo. Un tramo puede tener varios históricos (por año).

create table if not exists historicos (
    id          uuid primary key default gen_random_uuid(),
    tramo       text not null,
    tipo        text not null default 'CIPS',      -- CIPS | PAP | DCVG
    periodo     text,                               -- p.ej. 'Nov 2023'
    fecha       date,                               -- fecha de referencia (opcional)
    fuente      text,                               -- nombre del archivo origen
    puntos      jsonb,                              -- [{abscisa, on, off}, ...]
    resumen     jsonb,                              -- {n, pct_prot, prom_off, min_off, max_off, fuera}
    creado_en   timestamptz not null default now()
);
create index if not exists idx_historicos_tramo on historicos (lower(tramo), tipo, creado_en desc);

-- ── Seguridad ───────────────────────────────────────────────────────────────
alter table historicos enable row level security;

-- El portal (anon) puede LEER los históricos; la escritura queda para la app de
-- procesamiento (service_role, omite RLS).
drop policy if exists "lectura portal historicos" on historicos;
create policy "lectura portal historicos" on historicos
    for select to anon, authenticated using (true);
