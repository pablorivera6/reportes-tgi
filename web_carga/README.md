# Carga de campo TGI — web estática (reemplaza la Streamlit de uploads)

Formulario **mobile-first** para que los técnicos suban la información de campo
desde el celular. **Sitio estático** (HTML/JS puro) → **nunca se duerme**, carga
instantánea. Escribe directo a **Supabase** (mismo bucket `cargas` y misma tabla
`cargas` que usaba la app Streamlit), así que la app de procesamiento lo lee igual.

## Archivos

| Archivo | Qué es |
|---|---|
| `index.html` | La página (estilos mobile-first, marca PCC) |
| `app.js` | Lógica: valida, sube a Storage y crea la carga |
| `config.js` | URL + **llave pública** de Supabase + código de acceso opcional |
| `data.js` | Tramos + catálogo de casillas (**generado**, no editar a mano) |
| `vercel.json` | Config de despliegue |

## Puesta en marcha (una sola vez)

1. **Base de datos** — en Supabase → SQL Editor, corre `portal/schema_v8.sql`.
   Da permiso al público (llave anon) de **solo insertar** cargas y subir archivos.
2. **Despliegue en Vercel**:
   - Nuevo proyecto → conecta el repo → **Root Directory = `web_carga`**.
   - Framework: **Other** (es estático, sin build). Deploy.
   - (O con CLI: `cd web_carga && vercel --prod`.)
3. Comparte la URL a los técnicos. Listo.

## Seguridad

- La llave de `config.js` es la **anon/pública** de Supabase: es segura de exponer
  en el navegador. La protección real la da **RLS** (`schema_v8.sql`): con esa llave
  **solo se puede crear cargas y subir archivos**, nunca leer, listar ni borrar.
- `ACCESS_CODE` en `config.js` es un candado **opcional** de comodidad (vacío = abierto,
  igual que la app anterior). No es seguridad fuerte; la seguridad es el RLS.

## Mantenimiento

- Si cambian los **tramos** o el **catálogo de casillas**, regenera `data.js`:
  ```bash
  python3 exportar_datos_carga.py
  ```
  y vuelve a desplegar (o Vercel redepliega solo al hacer push).
- Las casillas por tipo (CIPS/PAP/DCVG) son las mismas de `entrega.CATALOGO`.
