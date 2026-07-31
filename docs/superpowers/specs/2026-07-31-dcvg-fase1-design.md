# Informe DCVG — Diseño (Fase 1)

Añade la generación de informes **DCVG** (Direct Current Voltage Gradient) a la
app de reportes TGI/OCENSA, junto a PAP y CIPS. Debe funcionar para cualquier
tramo. Se implementa en **2 fases**; este spec cubre la **Fase 1**.

## Alcance

- **Fase 1 (este spec):** informe DCVG a partir de los **2 FastField** (DCVG y
  Resistividades): hojas *Inspección DCVG*, *Resistividad*, *Informe*,
  *Hallazgos*, y las 2 gráficas resumen (*GRAFICA DCVG*, *Gráfica
  Resistividad*).
- **Fase 2 (después):** hojas por rango (~5 km) con el voltaje DCVG del logger
  de campo (*DCVG MONTENEGRO*: Survey Data → DCVG Voltage), creadas
  dinámicamente según la extensión del tramo.

## Entradas (Fase 1)

En la app, con Tipo Inspección = **DCVG**, se suben 2 archivos:

1. **DCVG FastField** (`Dcvg Fastfield.xlsx`): export de FastField.
   - Hoja `Root`: metadata — `Contratista`, `Fecha`, `Cliente`,
     `Troncal o ramal inspeccionado`, `Técnico a cargo`.
   - Hoja `subform_5` = **postes**: `Tipo de poste`, `PK`, `ON`, `OFF`,
     `Voltaje AC`, `Resistencia`, estados, `Coordenadas` ("lat,lon").
   - Hoja `subform_9` = **defectos**: `Sector`, `Ubicación` ("lat,lon"),
     `PK del defecto (Abscisa)` ("5+760"), `Forma N/S/E/O`, `OL/RE`,
     `Profundidad (M)`, `Clasificación`, `Forma del defecto` (posición reloj),
     `Comentarios`, `Caracter de la indicación` ("Catódico-Catódico", …).
2. **Resistividades FastField** (`Resistividades Fastfield.xlsx`): hoja
   `subform_7` — `PK`, `Sector`, `Profundidad`, `Ubicación` ("lat,lon"),
   `Resistencia 1/2/3 metros`.

Plantilla de salida: **`DCVG_REP.xlsx`** (13 hojas; zona de datos de
*Inspección DCVG* filas 8–238, bloque de firmas en 239; *Resistividad* con
fórmulas de ρ ya incluidas).

## Módulos nuevos

### `dcvg_reader.py`
- `leer_dcvg_fastfield(ruta) -> dict` con:
  - `meta`: contratista, fecha, cliente, tramo, tecnico.
  - `postes`: lista de dicts {tipo, pk_m, on, off, vac, resistencia, lat, lon}.
  - `defectos`: lista de dicts {sector, lat, lon, pk_m, forma_n/s/e/o, ol_re,
    profundidad, clasificacion_campo, posicion_reloj, comentarios, caracter}.
- `leer_resistividades_fastfield(ruta) -> list` de dicts {pk_m, sector,
  profundidad, lat, lon, r1, r2, r3}.
- `parse_pk(texto) -> int|None`: "5+760"→5760, "136+300"→136300 (reusa la
  lógica de abscisa por etiqueta ya probada en CIPS).
- `parse_coords(texto) -> (lat, lon)`: "4.5290577,-75.74…" → floats.
- `caracter_corto(txt) -> "AA"|"CA"|"CC"`: "Catódico-Catódico"→"CC",
  "Catódico-Anódico"→"CA", "Anódico-Anódico"→"AA".

### `dcvg_generator.py` (o métodos en `generator.py`)
- `fill_dcvg(postes, defectos)`: escribe la hoja *Inspección DCVG*.
- `fill_resistividad(resist)`: escribe la hoja *Resistividad*.
- Reutiliza `fill_general_info`, `fill_hallazgos`, y el patrón de ajuste de
  gráficas (`fill_graficas_*`).

## Hoja *Inspección DCVG* — mapeo de columnas

Postes y defectos se **unen y ordenan por abscisa** (col D). Fila inicial 8.

| Col | Encabezado | Poste (subform_5) | Defecto (subform_9) |
|-----|-----------|-------------------|---------------------|
| A | ÍTEM | correlativo | correlativo |
| B | REFERENCIAS GEOGRÁFICAS | `Tipo de poste` | "Defecto" |
| C | DISTANCIA TRAMO [m] | fórmula `=D{r}-$D$8` | igual |
| D | ABSCISA | `parse_pk(PK)` | `parse_pk(PK del defecto)` |
| E/F/G | LAT/LON/ALT | de `Coordenadas` | de `Ubicación` |
| H/I/J/K | FORMA [mV] 12/3/6/9 | — | **N→H, E→I, S→J, O→K** |
| L | CARÁCTER (ON-OFF) | — | `caracter_corto` (AA/CA/CC) |
| M | OL/RE [mV] | — | `OL/RE` |
| N/O | POT. ESTRUCTURA ON/OFF | `ON`/`OFF` | — |
| P | PULSO [mV] | fórmula `=ABS(N{r}-O{r})` | — |
| Q | P/RE [mV] | — | **interpolación** (ver abajo) |
| R | PROFUNDIDAD | — | `Profundidad (M)` |
| S/T/U | SEVERIDAD %IR (AA/CA/CC) | — | `=(M{r}/Q{r})*100` en la col del carácter |
| V | SEVERIDAD CLASIFICACIÓN | — | por umbrales de %IR |
| W | RESISTIVIDAD | (opcional Fase 1) | (opcional Fase 1) |
| X | OBSERVACIONES | `Tipo de poste` | `Comentarios`/"Defecto" |

### Cálculo del %IR (replicando el informe terminado)
- **Pulso** en cada poste: `P{r} = ABS(N{r}-O{r})`.
- **P/RE** en un defecto: interpolación lineal del pulso entre el poste
  anterior (`pa`) y el siguiente (`ps`) por abscisa:
  `Q{r} = ((P{ps}-P{pa})/(D{ps}-D{pa})*(D{r}-D{pa})) + P{pa}`.
- **%IR** = `=(M{r}/Q{r})*100`, escrito en **S** si carácter AA, **T** si CA,
  **U** si CC.
- **Clasificación** (V), por el valor de %IR:
  `1–15 Muy Pequeño · 16–35 Pequeño · 36–60 Mediano · 61–100 Grande`.

Se replican como **fórmulas de Excel** (no valores) para que el ingeniero pueda
ajustar en el archivo, igual que el informe terminado de referencia.

## Hoja *Resistividad* — mapeo

De `subform_7`, desde la fila 9 (fila 8 = encabezados con las fórmulas ρ ya
puestas por la plantilla): A=`parse_pk(PK)`, B=`Sector`, C/D=lat/lon (de
`Ubicación`), E=`Profundidad`, F=`Resistencia 1 metro`, H=`Resistencia 2
metros`, J=`Resistencia 3 metros`. Las columnas ρ1/ρ2/ρ3 y la clasificación de
corrosividad ya son fórmulas del template (`=2*PI()*a*R`).

## Informe y Hallazgos
- `fill_general_info` con la metadata del `Root` (fecha, cliente/gasoducto,
  tramo, técnico, contratista).
- `fill_hallazgos`: cada **defecto** como hallazgo (abscisa, coords, tipo =
  clasificación de severidad, descripción = comentarios/forma), reusando el
  `cips_a_hallazgos`/`fill_hallazgos` existente.

## Gráficas resumen
- `GRAFICA DCVG` y `Gráfica Resistividad`: ajustar el rango de las series de
  datos a las N filas escritas (mismo patrón que `fill_graficas_cips`), sin
  tocar las líneas/criterios que ya trae el template.

## Integración en las apps
- **streamlit_app.py** y **app.py**: cuando `tipo_inspeccion == 'DCVG'`, usar
  `DCVG_REP.xlsx`. Sección/tab para subir los 2 FastField. Reusar el patrón de
  "Procesar" y descarga.
- El selector Tipo Inspección ya incluye "DCVG".

## Errores y validación
- Archivo sin las hojas esperadas (`Root`/`subform_*`) → mensaje claro.
- PK no parseable → esa fila se omite con aviso (no rompe).
- Coordenadas vacías → celda vacía, no crash.
- **TDD** con `dcvg_reader` (parseos) y `fill_dcvg`/`fill_resistividad`
  (celdas y fórmulas correctas), validando end-to-end con los archivos reales
  de **Montenegro** (Dcvg Fastfield + Resistividades Fastfield).

## Fuera de alcance (Fase 2)
- Hojas por rango (~5 km) y gráficas del voltaje DCVG del logger de campo.
- Fotos de defectos (multiphoto_picker) — se evaluará luego.
