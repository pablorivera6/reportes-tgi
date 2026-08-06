-- ============================================================================
-- Portal TGI — Esquema v5: Cola de webhooks de FastField
-- Pegar en: Supabase → SQL Editor → New query → Run  (idempotente)
-- ============================================================================
-- Cuando un técnico envía una inspección en FastField, FastField llama a la
-- Edge Function 'fastfield-webhook', que solo inserta una fila aquí (el "buzón").
-- Luego la app de procesamiento drena esta cola: baja el envío + fotos, lo
-- traduce y crea la carga correspondiente en la tabla 'cargas'.

create table if not exists fastfield_cola (
    id             uuid primary key default gen_random_uuid(),
    submission_id  text not null,                        -- id del envío en FastField
    form_id        text,                                 -- id del formulario (FORM_MAP)
    form_name      text,
    estado         text not null default 'nuevo',        -- nuevo | procesada | error
    carga_id       uuid references cargas(id),           -- carga creada al procesar
    error          text,                                 -- detalle si falló
    payload        jsonb,                                -- copia del POST de FastField (auditoría)
    recibido_en    timestamptz not null default now(),
    procesada_en   timestamptz,
    -- un mismo submission no debe entrar dos veces
    constraint uq_fastfield_submission unique (submission_id)
);
create index if not exists idx_ffcola_estado on fastfield_cola(estado, recibido_en desc);

-- ── Seguridad ───────────────────────────────────────────────────────────────
-- Igual que 'cargas': solo service_role (Edge Function + app de procesamiento)
-- accede. Habilitamos RLS y NO creamos políticas para anon -> anon sin acceso.
alter table fastfield_cola enable row level security;
