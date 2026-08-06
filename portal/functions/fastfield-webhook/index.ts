// ============================================================================
// Edge Function: fastfield-webhook  (el "buzón")
// ----------------------------------------------------------------------------
// FastField llama aquí cada vez que un técnico ENVÍA una inspección
// (Data Destinations → Webhook). Esta función NO procesa nada: solo valida un
// secreto compartido y guarda el submissionId en la tabla `fastfield_cola`.
// Luego la app de procesamiento drena la cola (baja el envío + fotos, traduce
// y crea la carga) reusando el código Python ya probado.
//
// Variables de entorno (Supabase → Edge Functions → Secrets):
//   WEBHOOK_SECRET                -> secreto que también se configura en FastField
//   SUPABASE_URL                  -> lo inyecta Supabase automáticamente
//   SUPABASE_SERVICE_ROLE_KEY     -> lo inyecta Supabase automáticamente
//
// Despliegue:
//   supabase functions deploy fastfield-webhook --no-verify-jwt
//   supabase secrets set WEBHOOK_SECRET="<un-secreto-largo>"
// ============================================================================

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const WEBHOOK_SECRET = Deno.env.get("WEBHOOK_SECRET") ?? "";

// Busca una clave (varias variantes) en un objeto, incluso anidado 1 nivel.
function pick(obj: Record<string, unknown>, ...keys: string[]): string | null {
  for (const k of keys) {
    const v = obj?.[k];
    if (v !== undefined && v !== null && String(v).trim() !== "") return String(v);
  }
  // buscar un nivel adentro (FastField a veces envuelve en 'data'/'result'/'submission')
  for (const wrap of ["data", "result", "submission", "formResult", "payload"]) {
    const inner = obj?.[wrap];
    if (inner && typeof inner === "object") {
      const r = pick(inner as Record<string, unknown>, ...keys);
      if (r) return r;
    }
  }
  return null;
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  // ── Validar secreto (header o query param) ────────────────────────────────
  const url = new URL(req.url);
  const provided =
    req.headers.get("x-webhook-secret") ??
    req.headers.get("x-fastfield-secret") ??
    url.searchParams.get("secret") ??
    "";
  if (!WEBHOOK_SECRET || provided !== WEBHOOK_SECRET) {
    return new Response(JSON.stringify({ ok: false, error: "unauthorized" }), {
      status: 401,
      headers: { "content-type": "application/json" },
    });
  }

  // ── Leer el cuerpo (JSON) ─────────────────────────────────────────────────
  let body: Record<string, unknown> = {};
  try {
    body = await req.json();
  } catch (_) {
    return new Response(JSON.stringify({ ok: false, error: "bad json" }), {
      status: 400,
      headers: { "content-type": "application/json" },
    });
  }

  const submissionId = pick(body, "submissionId", "submission_id", "id");
  const formId = pick(body, "formId", "form_id");
  const formName = pick(body, "formName", "form_name", "name");

  if (!submissionId) {
    return new Response(
      JSON.stringify({ ok: false, error: "missing submissionId" }),
      { status: 422, headers: { "content-type": "application/json" } },
    );
  }

  // ── Insertar en la cola (idempotente por unique(submission_id)) ───────────
  const resp = await fetch(`${SUPABASE_URL}/rest/v1/fastfield_cola`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "apikey": SERVICE_KEY,
      "authorization": `Bearer ${SERVICE_KEY}`,
      // si ya existe ese submission, no duplicar ni fallar
      "prefer": "resolution=ignore-duplicates,return=minimal",
    },
    body: JSON.stringify({
      submission_id: submissionId,
      form_id: formId,
      form_name: formName,
      payload: body,
    }),
  });

  if (!resp.ok && resp.status !== 409) {
    const txt = await resp.text();
    return new Response(
      JSON.stringify({ ok: false, error: "db insert failed", detail: txt }),
      { status: 500, headers: { "content-type": "application/json" } },
    );
  }

  return new Response(
    JSON.stringify({ ok: true, submissionId, formId }),
    { status: 200, headers: { "content-type": "application/json" } },
  );
});
