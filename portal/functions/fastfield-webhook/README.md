# Edge Function: `fastfield-webhook`

El "buzón" que recibe el aviso de FastField cada vez que un técnico envía una
inspección. **No procesa nada**: valida un secreto y guarda el `submissionId`
en la tabla `fastfield_cola`. La app de procesamiento drena esa cola.

## 1. Requisito previo
Aplicar `portal/schema_v5.sql` en Supabase (crea `fastfield_cola`).

## 2. Desplegar la función
Necesitas la [Supabase CLI](https://supabase.com/docs/guides/cli) instalada y
haber hecho `supabase login`.

```bash
# desde la raíz del repo (donde está la carpeta portal/)
supabase link --project-ref nvsnovulwtnbgopyiyal          # una sola vez
# la CLI espera las funciones en supabase/functions/, así que copiamos/enlazamos:
mkdir -p supabase/functions
cp -R portal/functions/fastfield-webhook supabase/functions/

supabase functions deploy fastfield-webhook --no-verify-jwt
supabase secrets set WEBHOOK_SECRET="PON-AQUI-UN-SECRETO-LARGO-Y-ALEATORIO"
```

`SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` los inyecta Supabase solo; no hay
que setearlos.

La URL de la función queda así:
```
https://nvsnovulwtnbgopyiyal.functions.supabase.co/fastfield-webhook
```

## 3. Configurar el webhook en FastField (uno por formulario)
En FastField: **Forms → [formulario] → Data Destinations → Add → Webhook**
- **URL:** la de arriba
- **Method:** POST
- **Custom header:** `x-webhook-secret: <el mismo WEBHOOK_SECRET>`
  (o, si no admite headers, añade `?secret=<WEBHOOK_SECRET>` al final de la URL)
- **Payload:** el JSON completo del envío (por defecto). La función solo necesita
  que venga el `submissionId` en algún lado.

Repetir para los formularios: **Inspección DCVG** (1160295),
**Inspeccion PAP-PBI** (1199286) y **Aislamientos** (1240049).

## 4. Probar
```bash
curl -X POST "https://nvsnovulwtnbgopyiyal.functions.supabase.co/fastfield-webhook" \
  -H "content-type: application/json" \
  -H "x-webhook-secret: <WEBHOOK_SECRET>" \
  -d '{"submissionId":"54041e96-687c-445f-9fae-20202ef0757b","formId":"1160295","formName":"Inspección DCVG"}'
# -> {"ok":true,...}  y aparece una fila en fastfield_cola
```
