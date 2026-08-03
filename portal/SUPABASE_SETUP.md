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
