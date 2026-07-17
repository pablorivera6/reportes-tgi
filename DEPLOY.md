# Desplegar la app web en Streamlit Community Cloud

La app web (`streamlit_app.py`) usa el mismo motor que la app de escritorio.

> **Importante (2026):** el plan gratuito de Streamlit Cloud ya **no** soporta
> apps privadas desde GitHub (eso se movió a Snowflake, de pago). El esquema
> vigente es: **repo público + app pública con contraseña de equipo**.

## Esquema de seguridad

- El repo `pablorivera6/reportes-tgi` es **público**. Por eso NO contiene
  `Listado equipos TGI.xlsx` (nombres de inspectores y seriales). El
  autollenado de equipos no está disponible en la nube.
- La app pide **contraseña** al entrar. Se define en Secrets (abajo). Sin ese
  secret el candado queda desactivado (útil en desarrollo local).

## Pasos de despliegue

1. Entra a **https://share.streamlit.io** → **Create app** →
   *Deploy a public app from GitHub*.
2. Repository: `pablorivera6/reportes-tgi` · Branch: `main` ·
   Main file path: `streamlit_app.py` → **Deploy**.
3. En **App settings → Secrets**, pega (con tus valores reales):

   ```toml
   [app]
   password = "CONTRASEÑA_DEL_EQUIPO"

   [gemini]
   api_key = "TU_LLAVE_DE_GEMINI"
   ```

   - Sin `[app] password` la app queda abierta a cualquiera con el link.
   - Sin `[gemini] api_key` la app funciona pero la clasificación de fotos
     con IA queda desactivada (solo palabras clave del nombre).

## Actualizar la app

Cualquier `git push` a `main` redespliega automáticamente en ~1 minuto.
**OJO:** haz el push desde `/private/tmp/tgi_push`, nunca desde el Desktop
(iCloud cuelga los pushes — ver BUILD.md).

## Notas del plan gratuito

- Tras varios días sin uso la app "duerme": el primer acceso tarda ~1 minuto.
- Límite de subida por archivo: 200 MB (de sobra para los Excel de campo).
