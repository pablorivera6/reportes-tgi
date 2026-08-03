-- ============================================================================
-- Portal TGI — Esquema v4: Fase de aprobación de inspecciones
-- Pegar en: Supabase → SQL Editor → New query → Run  (idempotente)
--
-- Cada inspección nace "en_revision" (NO visible al cliente TGI). Un ingeniero
-- revisor la aprueba y RECIÉN ahí aparece en el portal. La restricción es a
-- nivel de base de datos (RLS): el login TGI (anon) solo puede leer aprobadas.
-- El revisor y la app de procesamiento usan service_role (omiten RLS).
-- ============================================================================

alter table inspecciones add column if not exists estado        text not null default 'en_revision';
alter table inspecciones add column if not exists revisado_por   text;
alter table inspecciones add column if not exists revisado_en    timestamptz;
alter table inspecciones add column if not exists nota_revision  text;

-- Aprueba lo que YA existía (las inspecciones demo) para que no desaparezcan.
update inspecciones set estado = 'aprobada' where estado is null or estado = 'en_revision';

create index if not exists idx_insp_estado on inspecciones(estado, creado_en desc);

-- ── RLS: anon (TGI) solo ve APROBADAS ───────────────────────────────────────
drop policy if exists "lectura portal inspecciones" on inspecciones;
drop policy if exists "lectura portal inspecciones aprobadas" on inspecciones;
create policy "lectura portal inspecciones aprobadas" on inspecciones
    for select to anon, authenticated using (estado = 'aprobada');

-- Tablas hijas: para anon, solo filas de inspecciones aprobadas.
do $$
declare t text;
begin
  foreach t in array array['puntos_cips','hallazgos','tramos_no_inspeccionados',
                           'puntos_pap','postes_dcvg','defectos_dcvg','resistividades_dcvg']
  loop
    execute format('drop policy if exists "lectura portal %1$s aprob" on %1$s;', t);
    execute format($f$create policy "lectura portal %1$s aprob" on %1$s
        for select to anon, authenticated
        using (inspeccion_id in (select id from inspecciones where estado = 'aprobada'));$f$, t);
  end loop;
end $$;

-- Nota: las políticas SELECT antiguas con using(true) de las tablas hijas se
-- reemplazan arriba. Si quedaran duplicadas, elimínalas manualmente; PostgreSQL
-- aplica OR entre políticas, así que la más permisiva ganaría.
drop policy if exists "lectura portal puntos" on puntos_cips;
drop policy if exists "lectura portal hallazgos" on hallazgos;
drop policy if exists "lectura portal tramos" on tramos_no_inspeccionados;
drop policy if exists "lectura portal pap" on puntos_pap;
drop policy if exists "lectura portal postes" on postes_dcvg;
drop policy if exists "lectura portal defectos" on defectos_dcvg;
drop policy if exists "lectura portal resist" on resistividades_dcvg;
