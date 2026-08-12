-- ============================================================================
-- Portal TGI — Esquema v8: Carga de campo desde web estática (Vercel + Supabase)
-- Pegar en: Supabase → SQL Editor → New query → Run  (idempotente)
-- ============================================================================
-- Permite que el formulario web de los técnicos (sitio estático, usa la llave
-- PÚBLICA anon) suba archivos y registre la carga, SIN exponer el service_key.
--
-- Seguridad: el rol `anon` SOLO puede INSERTAR (crear cargas y subir archivos).
-- NO puede leer, listar, modificar ni borrar nada. En el peor caso, alguien con
-- la llave pública podría crear una carga basura — nunca leer ni borrar datos.
-- La app de procesamiento (service_role) sigue siendo la única que lee/gestiona.

-- ── Tabla `cargas`: permitir INSERT del anon (estado forzado a 'pendiente') ───
alter table cargas enable row level security;

drop policy if exists "carga web insert" on cargas;
create policy "carga web insert" on cargas
    for insert to anon
    with check (estado = 'pendiente');

-- (No se crea policy de SELECT/UPDATE/DELETE para anon: quedan bloqueadas.)

-- ── Storage: bucket privado `cargas` + INSERT (upload) del anon ───────────────
-- El bucket ya existe (lo usa la app de procesamiento); esto lo asegura privado.
insert into storage.buckets (id, name, public)
    values ('cargas', 'cargas', false)
    on conflict (id) do nothing;

drop policy if exists "carga web upload" on storage.objects;
create policy "carga web upload" on storage.objects
    for insert to anon
    with check (bucket_id = 'cargas');

-- (Sin policy de SELECT/UPDATE/DELETE para anon en storage.objects del bucket
--  cargas: el técnico puede subir pero no leer ni borrar.)
