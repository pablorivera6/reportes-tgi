# Integración del procesamiento CIPS-LRS en la app ejecutable TGI

Fecha: 2026-07-16

## Objetivo

Reemplazar el procesamiento de datos CIPS de la app ejecutable (PyQt6) por el
motor LRS de la app de Streamlit `pablorivera6/proceso-cips`, conservando el
destino actual: la hoja **"Potenciales CIPS"** del informe TGI (`EN BLANCO.xlsx`).

## Contexto

Dos sistemas separados procesan CIPS hoy:

- **App ejecutable** (`cips_reader.py` + `app.py::load_cips`): usa el KMZ y
  corrección por distancia de hilo. Actualmente **crashea** al pulsar "Cargar
  Data CIPS" porque `load_cips` referencia `self.cmb_kmz_rutas`, un widget que
  nunca se crea (verificado ejecutando la app headless).
- **`proceso-cips`** (Streamlit): usa **shapefiles por tramo** y referenciación
  lineal (LRS) vía shapely/pyproj. Más robusto. Verificado corriendo de punta a
  punta en el Mac del proyecto (40 puntos sintéticos, clasificó 39 protegidos /
  1 desprotegido).

Decisión del usuario: copiar el procesamiento LRS **tal cual**, tomando la
geometría de los **shapefiles** (no del KMZ), y volcarlo en la hoja
"Potenciales CIPS" del informe.

## Qué se copia y qué se descarta de `proceso-cips`

| Archivo | Acción | Motivo |
|---|---|---|
| `mod_cips_lrs.py` | Copiar | Motor LRS: snap a traza, PK geométrico, auto-sentido, limpieza outliers, Estado_CP |
| `mod_unificar.py` | Copiar | Unifica varios Excel y arma columna `Comentarios` |
| `shapefiles/` (1.547 archivos, 259 tramos) | Copiar al bundle | Geometría del ducto elegida |
| `data/Listado de Infraestructura para Cod Informes.xlsx` | Copiar al bundle | Mapeo Empresa/Distrito/Tramo → `ID TRAMO` → shapefile |
| `mod_cips_sharepoint.py` | Descartar | Sincronización SharePoint; no aplica a app de escritorio |
| `app.py` (Streamlit) | Descartar | UI web; la ejecutable ya tiene UI PyQt6 |

## Arquitectura

### Flujo de datos

```
Archivos CIPS (.xlsx, del diálogo PyQt)
  └─> cips_lrs.py : procesar_cips_lrs(lista_archivos, shp_path)
        ├─ unificar (mod_unificar)
        └─ LRS (mod_cips_lrs)
        └─> DataFrame procesado
              └─> adaptador de esquema (LRS -> formato hoja CIPS)
                    └─> lista[dict]
                          └─> generator.fill_cips()  -> hoja "Potenciales CIPS"
```

### Piezas nuevas

1. **`cips_lrs.py`** — módulo autocontenido, sin Streamlit. Fusiona la lógica de
   `mod_unificar` + `mod_cips_lrs`. Punto de entrada:

   ```python
   def procesar_cips_lrs(lista_archivos_xlsx: list[str], shp_path: str,
                         carpeta_salida: str = None) -> tuple[str, pd.DataFrame]:
       """Unifica -> LRS. Devuelve (ruta_excel_procesado, DataFrame)."""
   ```

   Adaptación respecto al original: recibe **lista de rutas de archivo** (lo que
   entrega `QFileDialog.getOpenFileNames`) en lugar de un `glob` de carpeta.
   La lógica de cálculo LRS se conserva idéntica.

2. **Adaptador de esquema** — mapea columnas del DataFrame LRS al formato de
   dict que espera `generator.fill_cips()`:

   | Hoja "Potenciales CIPS" espera | Motor LRS produce |
   |---|---|
   | `abscisa` | `PK_geom_m` → formateo `K 000+000` |
   | `on_mv` / `off_mv` | `On_mV_limpio` / `Off_mV_limpio` |
   | `on_limpio` / `off_limpio` | igual |
   | `lat` / `lon` | `Lat_corr` / `Long_corr` (ya corregidas) |
   | `observaciones` / `referencia` | `Comentarios` |
   | `far_on/off`, `near_on/off`, `metal_on/off`, `vac` | **no los produce → vacío** |

   Las columnas Far/Near/Metal Ground y VAC quedan **vacías**, exactamente como
   las deja la app de Streamlit (decisión explícita del usuario).

3. **Selector Empresa/Distrito/Tramo** en la UI PyQt (tab "Datos Generales",
   junto al botón "Cargar Data CIPS"). Réplica del sidebar de Streamlit:
   - **Empresa**: TGI u OCENSA
   - TGI → **Distrito** (D1–D8) → **Tramo**
   - OCENSA → **Tramo** directo
   - Resuelve `ID TRAMO` vía el Excel de infraestructura → `shapefiles/<ID>.shp`
   - Backing data: `Listado de Infraestructura para Cod Informes.xlsx`
     (columnas `ID TRAMO`, `TRAMO`, `DISTRITO`; 284 filas; 217 con `.shp`).

4. **Reescritura de `load_cips`** — usa el flujo nuevo: lee el selector, resuelve
   el shapefile, corre `procesar_cips_lrs`, aplica el adaptador, guarda en
   `self.data['cips']` para que `generator.fill_cips` lo escriba. Se elimina la
   ruta vieja rota (KMZ + `cmb_kmz_rutas` + método de hilo).

## Dependencias

Ya en el bundle: `scipy`, `numpy`, `pandas`, `openpyxl`.
Nuevas a agregar (a `requirements.txt` y verificar empaquetado PyInstaller):
`pyproj`, `shapely`, `pyshp` (importa como `shapefile`), `scikit-learn`.

## Assets y empaquetado

- Copiar `shapefiles/` y `Listado de Infraestructura para Cod Informes.xlsx` a la
  carpeta del código fuente.
- Actualizar `TGI_Report_Generator.spec` (`datas`) para incluir ambos.
- Verificar que las nuevas libs GIS entren al PYZ/`_internal`.

## Manejo de errores

- Si no se encuentra shapefile para el tramo seleccionado → mensaje claro al
  usuario, no procesar.
- Si los archivos no tienen hoja "Survey Data" → mensaje claro.
- `load_cips` debe envolverse en try/except (el original no lo tenía → crash).

## Alcance explícito

- **Incluye:** motor LRS, adaptador, selector UI, reescritura de `load_cips`,
  assets, deps, `.spec`.
- **No incluye (por ahora):** los otros bugs de auditoría (VAC, hoja `pe`,
  duplicados, saldo de librerías no usadas). Se tratarán después.
- El destino de salida es la hoja "Potenciales CIPS" del informe TGI, confirmado
  por el usuario (la app "detecta que el archivo es CIPS y lo mete en esa hoja").

## Verificación

- Motor LRS ya verificado end-to-end en el Mac con datos sintéticos sobre un
  shapefile real (`R_ACA.shp`, 14.675 m).
- Pendiente en implementación: prueba del adaptador (LRS → dict → celdas de la
  hoja) y prueba de resolución shapefile desde el selector.
