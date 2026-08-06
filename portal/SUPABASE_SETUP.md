# Crear el proyecto Supabase (5 minutos)

Esto lo haces tú una sola vez. Al final me pasas **3 datos** y yo conecto todo.

## 1. Crear cuenta y proyecto
1. Entra a **https://supabase.com** → **Start your project** (puedes entrar con GitHub).
2. **New project**:
   - **Name**: `portal-tgi`
   - **Database Password**: pon una y **guárdala** (no la necesito yo).
   - **Region**: `East US (North Virginia)` (o la más cercana a Colombia).
   - **Plan**: Free.
3. Espera ~2 min a que se aprovisione.

## 2. Crear las tablas
1. Menú izquierdo → **SQL Editor** → **New query**.
2. Abre el archivo `portal/schema.sql` de este proyecto, **copia todo** y pégalo.
3. Clic en **Run** (abajo a la derecha). Debe decir *Success*.
   - Esto crea las 4 tablas, los índices, las políticas RLS y el bucket `informes`.

## 3. Copiar las llaves (lo que necesito)
Menú izquierdo → **Project Settings** (engranaje) → **API**:

- **Project URL** → algo como `https://xxxxxxxx.supabase.co`
- **Project API keys**:
  - **anon** `public` → para el **portal** (solo lectura)
  - **service_role** `secret` → para la **app de procesamiento** (escribe)

> ⚠️ La **service_role** es sensible (omite la seguridad). No la publiques en
> el repo ni la compartas por fuera. Va **solo** en los Secrets de la app de
> procesamiento.

## 4. Pásame estos 3 datos
```
SUPABASE_URL = https://xxxxxxxx.supabase.co
SUPABASE_ANON_KEY = eyJhbGciOi... (anon public)
SUPABASE_SERVICE_KEY = eyJhbGciOi... (service_role secret)
```

Con eso configuro los Secrets de las dos apps y queda funcionando la publicación
y el portal.

---

### ¿Dónde van los secrets? (lo hago yo, referencia)
- **App procesamiento** (`.streamlit/secrets.toml` local / Secrets en Streamlit Cloud):
  ```toml
  [supabase]
  url = "https://xxxxxxxx.supabase.co"
  service_key = "eyJhbGciOi...service_role..."
  [app]
  password = "clave-equipo-PCC"
  ```
- **App portal**:
  ```toml
  [supabase]
  url = "https://xxxxxxxx.supabase.co"
  anon_key = "eyJhbGciOi...anon..."
  [portal]
  password = "clave-cliente-TGI"
  ```

---

## FastField → app (webhook automático)

**Objetivo:** que las inspecciones enviadas en FastField lleguen solas a la
bandeja de la app, sin pegar `submissionId` a mano.

Pasos (una sola vez):
1. **SQL:** correr `portal/schema_v5.sql` (crea la cola `fastfield_cola`).
2. **Edge Function:** desplegar el "buzón" siguiendo
   `portal/functions/fastfield-webhook/README.md` y setear `WEBHOOK_SECRET`.
3. **Webhooks en FastField:** en cada formulario (DCVG 1160295, PAP 1199286,
   Aislamientos 1240049) → Data Destinations → Webhook → URL de la función +
   header `x-webhook-secret`.
4. **Secrets de la app de procesamiento** — añadir la sección:
   ```toml
   [fastfield]
   email = "data.ingenieria@proteccioncatodica.com"
   password = "..."          # ROTAR esta contraseña
   api_key = "67d6b9f74c3648af958327b0dc26ca54"
   ```

**Flujo:** técnico envía en FastField → webhook mete el envío en `fastfield_cola`
→ en la app, expander **"📡 Inspecciones nuevas de FastField"** → botón trae el
envío + fotos, lo traduce y lo deja como **carga pendiente** → de ahí sigue el
flujo normal (⚙️ Traer a la app y procesar → Generar → Publicar/Aprobar).

Estado de los transforms: **DCVG completo** (postes, defectos, resistividades,
hallazgos), **PAP** y **Aislamientos** ya mapeados en `fastfield_transform.py`.
El adaptador a la forma del generador está listo para **DCVG**; PAP/Aislamientos
por API quedan como siguiente paso (hoy entran por Excel).
