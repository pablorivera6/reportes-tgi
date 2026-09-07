# Devolución de informes rechazados — Plan de implementación

> **Para agentes:** SUB-SKILL REQUERIDA: usa `superpowers:subagent-driven-development`
> (recomendado) o `superpowers:executing-plans` para ejecutar este plan tarea por
> tarea. Los pasos usan casillas (`- [ ]`) para seguimiento.

**Goal:** Que un informe rechazado en el portal vuelva al generador con su
contexto intacto, y que Claude traduzca la nota del revisor en correcciones
concretas que el ingeniero aprueba una por una.

**Architecture:** El portal guarda el rechazo como N observaciones estructuradas
(`observaciones_revision`) en vez de un párrafo. La inspección guarda de dónde
salió (`carga_id`) y con qué se generó (`contexto` jsonb). El generador tiene un
buzón que rehidrata la sesión desde las filas que ya están en Supabase — sin
depender de los crudos — y republica actualizando la misma fila como Rev.B.
Claude entra en dos puntos acotados, detrás de un validador de lista blanca.

**Tech Stack:** Python 3, Streamlit, Supabase (Postgres + Storage), openpyxl,
pytest, SDK `anthropic`.

**Spec:** `docs/superpowers/specs/2026-09-02-devolucion-rechazos-design.md`

---

## Convenciones de este proyecto (leer antes de la Tarea 1)

**Ruta del proyecto** (tiene espacios — siempre entre comillas):

```
/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente
```

**Correr los tests** (el venv del Desktop no sirve; es el de `/private/tmp`):

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/ -q --ignore=tests/test_ui_cips_selector.py --ignore=tests/test_cips_duplicados.py
```

Si el venv no existe (a `/private/tmp` lo limpian):

```bash
python3 -m venv /private/tmp/venv_tgi && /private/tmp/venv_tgi/bin/pip install "numpy<2" "pandas<2.3" scipy scikit-learn pyproj shapely pyshp openpyxl pytest streamlit supabase anthropic
```

**NUNCA correr `git` desde el Desktop** — está en iCloud y se cuelga con
TimeoutError errno 60. Los commits van desde un clon en `/private/tmp`. Una vez
por sesión:

```bash
rm -rf /private/tmp/tgi_push && git clone https://github.com/pablorivera6/reportes-tgi.git /private/tmp/tgi_push
```

Cada paso de commit copia los archivos al clon y commitea ahí. `git add` y
`git commit` van en comandos SEPARADOS y el mensaje es de UNA sola línea (el
clasificador de auto-mode bloquea los compuestos).

**NO hacer push hasta la Tarea 19.** Cada push a `main` redespliega las 3 apps
de Streamlit Cloud a la vez.

---

## Estructura de archivos

| Archivo | Responsabilidad |
|---|---|
| `portal/schema_v9.sql` | **nuevo** · columnas `carga_id`/`contexto`/`revision` + tabla `observaciones_revision` |
| `revision.py` | **nuevo** · categorías de observación, mapeadores BD→generador, `rehidratar()`. Sin Streamlit, sin red. |
| `ia_revision.py` | **nuevo** · cliente Claude + validador de lista blanca. Sin Streamlit. |
| `db.py` | constructores de filas puros; `carga_id`/`contexto`/`revision`/`reemplaza_id`; CRUD de observaciones |
| `portal_app.py` | rechazo estructurado en `_barra_revision` |
| `streamlit_app.py` | buzón de rechazos, `carga_id`+`contexto` al publicar, republicar como revisión, diff aprobable |
| `nombres.py` | parámetro `revision` |

`revision.py` e `ia_revision.py` son módulos nuevos y pequeños a propósito:
`streamlit_app.py` ya tiene 1.599 líneas y `portal_app.py` 1.339. Toda la lógica
que se pueda probar sin Streamlit vive fuera de ellos.

---

# FASE 1 — La devolución (sin IA)

Funciona sola. Es donde está el ahorro de tiempo real.

---

### Task 1: Esquema v9 en Supabase

**Files:**
- Create: `portal/schema_v9.sql`

- [ ] **Step 1: Escribir el SQL**

```sql
-- ============================================================================
-- Portal TGI — Esquema v9: Devolución de informes rechazados
-- Pegar en: Supabase → SQL Editor → New query → Run  (idempotente)
--
-- Un rechazo deja de ser un párrafo y pasa a ser N observaciones con categoría
-- y ubicación. La inspección recuerda de dónde salió (carga_id) y con qué se
-- generó (contexto), que es lo que permite reabrirla en el generador.
-- ============================================================================

alter table inspecciones add column if not exists carga_id uuid references cargas(id);
alter table inspecciones add column if not exists contexto jsonb;
alter table inspecciones add column if not exists revision text not null default 'A';

create table if not exists observaciones_revision (
    id            bigserial primary key,
    inspeccion_id uuid not null references inspecciones(id) on delete cascade,
    categoria     text not null,   -- datos_generales|procesamiento|texto_campo|falta_info
    campo         text,            -- 'info.tramo', 'hallazgo.descripcion', ...
    abscisa_ini   integer,
    abscisa_fin   integer,
    nota          text,
    origen        text not null default 'revisor',   -- revisor | ia
    estado        text not null default 'abierta',   -- abierta | resuelta | descartada
    creado_en     timestamptz not null default now()
);
create index if not exists idx_obs_insp on observaciones_revision(inspeccion_id, estado);
create index if not exists idx_insp_rechazadas on inspecciones(estado, creado_en desc)
    where estado = 'rechazada';

-- Solo service_role (revisor + generador). El cliente TGI (anon) no ve rechazos.
alter table observaciones_revision enable row level security;
```

- [ ] **Step 2: El usuario lo corre en Supabase**

Este paso NO lo ejecuta el agente. Pídele al usuario que abra Supabase → SQL
Editor → New query, pegue el contenido de `portal/schema_v9.sql` y le dé Run.
Espera su confirmación antes de seguir.

- [ ] **Step 3: Verificar que la tabla existe**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -c "
import tomllib, db
with open('.streamlit/secrets.toml','rb') as f: s = tomllib.load(f)
db._secrets = lambda: s['supabase']
cli = db._client(write=True)
print('observaciones_revision OK:', cli.table('observaciones_revision').select('id').limit(1).execute().data)
print('columnas nuevas OK:', list((cli.table('inspecciones').select('id,carga_id,contexto,revision').limit(1).execute().data or [{}])[0].keys()))
"
```

Expected: `observaciones_revision OK: []` y una lista que incluya `carga_id`,
`contexto`, `revision`. Si sale `relation ... does not exist`, el SQL no se
corrió.

- [ ] **Step 4: Commit**

```bash
cp "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente/portal/schema_v9.sql" /private/tmp/tgi_push/portal/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(portal): esquema v9 para devolucion de rechazos"
```

---

### Task 2: Extraer los constructores de filas de `db.py` a funciones puras

Hoy las filas que se insertan se arman dentro de `guardar_inspeccion_*`, así que
no se pueden probar sin Supabase. Sacarlas a funciones puras es lo que hace
testeable el round-trip de la Tarea 3. **Refactor sin cambio de comportamiento.**

**Files:**
- Modify: `db.py` (dentro de `guardar_inspeccion_cips`, `guardar_inspeccion_pap`, `guardar_inspeccion_dcvg`)
- Test: `tests/test_revision_roundtrip.py` (se crea en la Tarea 3)

- [ ] **Step 1: Añadir `_puntos_cips_filas` justo antes de `guardar_inspeccion_cips`**

```python
def _puntos_cips_filas(insp_id, cips):
    """Filas de `puntos_cips` a partir de los dicts CIPS del generador.
    Pura: no toca red. `revision.cips_desde_filas` es su inversa."""
    filas = []
    for i, c in enumerate(cips, 1):
        off = (_f(c.get("off_limpio")) if c.get("off_limpio") is not None
               else _f(c.get("off_mv")))
        filas.append({
            "inspeccion_id": insp_id, "item": i,
            "abscisa": _i(c.get("abscisa_val")), "fecha": _fecha(c.get("fecha")),
            "on_mv": _f(c.get("on_mv")), "off_mv": _f(c.get("off_mv")),
            "on_limpio": _f(c.get("on_limpio")), "off_limpio": _f(c.get("off_limpio")),
            "natural_mv": _f(c.get("natural_mv")),
            "polarizacion_mv": _f(c.get("polarizacion_mv")),
            "vac_mv": _f(c.get("vac_mv")),
            "metal_on": _f(c.get("metal_on")), "metal_off": _f(c.get("metal_off")),
            "lejano_on": _f(c.get("far_on")), "lejano_off": _f(c.get("far_off")),
            "cercano_on": _f(c.get("near_on")), "cercano_off": _f(c.get("near_off")),
            "ir_on_off": _f(c.get("ir_on_off")),
            "lat": _f(c.get("lat")), "lon": _f(c.get("lon")),
            "observaciones": (c.get("observaciones") or c.get("referencia") or None),
            "estado": estado_cp(off),
        })
    return filas
```

- [ ] **Step 2: Reemplazar el bloque inline de `guardar_inspeccion_cips`**

En `guardar_inspeccion_cips`, borra el bloque que empieza en `# Puntos CIPS` con
`puntos = []` y su `for`, y déjalo así:

```python
    # Puntos CIPS
    _insert_lotes(cli, "puntos_cips", _puntos_cips_filas(insp_id, cips))
```

- [ ] **Step 3: Añadir `_puntos_pap_filas` antes de `guardar_inspeccion_pap`**

```python
def _puntos_pap_filas(insp_id, potenciales):
    """Filas de `puntos_pap`. Pura. Inversa: `revision.pap_desde_filas`."""
    def _absc(p):
        return _i(p.get("abscisa") if p.get("abscisa") is not None else p.get("pk_m"))

    def _off(p):
        return _f(p.get("off_mv") if p.get("off_mv") is not None else p.get("off"))

    def _on(p):
        return _f(p.get("on_mv") if p.get("on_mv") is not None else p.get("on"))

    filas = []
    for i, p in enumerate(potenciales, 1):
        off = _off(p)
        filas.append({
            "inspeccion_id": insp_id, "item": i, "abscisa": _absc(p),
            "fecha": _fecha(p.get("fecha")), "on_mv": _on(p), "off_mv": off,
            "natural_mv": _f(p.get("potencial_natural")),
            "polarizacion_mv": _f(p.get("polarizacion")),
            "vac_mv": _f(p.get("vac")), "ir_on_off": _f(p.get("ir_on_off")),
            "resistencia": _f(p.get("resistencia")),
            "lat": _f(p.get("lat")), "lon": _f(p.get("lon")),
            "ref_geografica": p.get("ref_geografica"),
            "observaciones": p.get("observaciones"), "estado": estado_cp(off),
        })
    return filas
```

- [ ] **Step 4: Usarla en `guardar_inspeccion_pap`**

Borra el `filas = []` con su `for` y deja:

```python
    _insert_lotes(cli, "puntos_pap", _puntos_pap_filas(insp_id, potenciales))
```

Ojo: `guardar_inspeccion_pap` sigue necesitando sus `_absc`/`_off` locales para
el resumen; NO los borres, solo el bloque de construcción de `filas`.

- [ ] **Step 5: Añadir los tres constructores DCVG antes de `guardar_inspeccion_dcvg`**

```python
def _postes_dcvg_filas(insp_id, postes):
    """Filas de `postes_dcvg`. Pura. Inversa: `revision.postes_desde_filas`."""
    return [{
        "inspeccion_id": insp_id, "item": i, "abscisa": _i(p.get("pk_m")),
        "tipo": p.get("tipo"), "on_mv": _f(p.get("on")), "off_mv": _f(p.get("off")),
        "vac_mv": _f(p.get("vac")), "resistencia": _f(p.get("resistencia")),
        "lat": _f(p.get("lat")), "lon": _f(p.get("lon")),
    } for i, p in enumerate(postes or [], 1)]


def _defectos_dcvg_filas(insp_id, defectos, sev):
    """Filas de `defectos_dcvg`. `sev` viene de `_severidad_dcvg` (derivados).
    Pura. Inversa: `revision.defectos_desde_filas` (que NO devuelve derivados)."""
    return [{
        "inspeccion_id": insp_id, "item": i, "abscisa": _i(d.get("pk_m")),
        "sector": d.get("sector"),
        "forma_n": _f(d.get("forma_n")), "forma_e": _f(d.get("forma_e")),
        "forma_s": _f(d.get("forma_s")), "forma_o": _f(d.get("forma_o")),
        "caracter": d.get("caracter"), "ol_re": _f(d.get("ol_re")),
        "p_re": sev[i - 1]["p_re"], "severidad_pct": sev[i - 1]["severidad_pct"],
        "clasificacion": sev[i - 1]["clasificacion"],
        "profundidad": _f(d.get("profundidad")),
        "posicion_reloj": d.get("posicion_reloj"),
        "lat": _f(d.get("lat")), "lon": _f(d.get("lon")),
        "comentarios": d.get("comentarios"),
    } for i, d in enumerate(defectos or [], 1)]


def _resist_dcvg_filas(insp_id, resistividades):
    """Filas de `resistividades_dcvg`. Pura. Inversa: `revision.resist_desde_filas`."""
    return [{
        "inspeccion_id": insp_id, "item": i, "abscisa": _i(r.get("pk_m")),
        "sector": r.get("sector"), "profundidad": _f(r.get("profundidad")),
        "r1": _f(r.get("r1")), "r2": _f(r.get("r2")), "r3": _f(r.get("r3")),
        "lat": _f(r.get("lat")), "lon": _f(r.get("lon")),
    } for i, r in enumerate(resistividades or [], 1)]
```

- [ ] **Step 6: Usarlas en `guardar_inspeccion_dcvg`**

Reemplaza las tres llamadas `_insert_lotes(...)` con sus comprensiones inline por:

```python
    _insert_lotes(cli, "postes_dcvg", _postes_dcvg_filas(insp_id, postes))
    _insert_lotes(cli, "defectos_dcvg", _defectos_dcvg_filas(insp_id, defectos, sev))
    _insert_lotes(cli, "resistividades_dcvg", _resist_dcvg_filas(insp_id, resistividades))
```

- [ ] **Step 7: Verificar que no se rompió nada**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_db.py -q
```

Expected: PASS (los mismos tests que antes; es un refactor).

- [ ] **Step 8: Commit**

```bash
cp "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente/db.py" /private/tmp/tgi_push/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "refactor(db): constructores de filas puros y testeables"
```

---

### Task 3: `revision.py` — mapeador inverso CIPS

**Files:**
- Create: `revision.py`
- Create: `tests/test_revision_roundtrip.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""El mapeador inverso BD→generador. Si esto se desincroniza, el informe
corregido sale con datos corridos y NADIE se entera: no revienta."""
import db
import revision


CIPS_ORIG = [{
    "abscisa_val": 1200, "fecha": "2026-03-04",
    "on_mv": -1500.0, "off_mv": -900.0,
    "on_limpio": -1490.0, "off_limpio": -905.0,
    "natural_mv": -600.0, "polarizacion_mv": -305.0, "vac_mv": 2.5,
    "metal_on": -1.1, "metal_off": -0.9,
    "far_on": -1.2, "far_off": -0.95,
    "near_on": -1.05, "near_off": -0.9,
    "ir_on_off": 595.0, "lat": 4.1, "lon": -75.2,
    "observaciones": "cruce de via",
}]


def test_cips_round_trip_conserva_todas_las_claves():
    filas = db._puntos_cips_filas("insp-1", CIPS_ORIG)
    vuelta = revision.cips_desde_filas(filas)
    assert len(vuelta) == 1
    for k, v in CIPS_ORIG[0].items():
        assert vuelta[0][k] == v, f"se perdio o cambio '{k}'"


def test_cips_no_devuelve_columnas_de_bd_ni_derivados():
    filas = db._puntos_cips_filas("insp-1", CIPS_ORIG)
    vuelta = revision.cips_desde_filas(filas)
    for prohibido in ("inspeccion_id", "item", "estado", "abscisa",
                      "lejano_on", "cercano_on"):
        assert prohibido not in vuelta[0]
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_revision_roundtrip.py -q
```

Expected: FAIL con `ModuleNotFoundError: No module named 'revision'`.

- [ ] **Step 3: Escribir `revision.py` con el mapeador CIPS**

```python
"""Devolución de informes rechazados: modelo de observaciones y rehidratación.

La inversa de los constructores `db._*_filas`. Las columnas de la BD y las
claves que espera el generador NO se llaman igual (`abscisa` vs `abscisa_val`,
`lejano_on` vs `far_on`), así que el mapeo es explícito y está cubierto por
tests de ida y vuelta: si se desincroniza, el informe corregido sale con datos
corridos sin lanzar ningún error.

Los campos DERIVADOS (`estado`, `p_re`, `severidad_pct`, `clasificacion`) no se
rehidratan: `dashboard.estado_cp` y `db._severidad_dcvg` los recalculan al
publicar. Eso elimina el riesgo de que un % vuelva como fracción.

Sin Streamlit y sin red: todo aquí es puro.
"""
from __future__ import annotations

# ── Mapeos columna BD → clave del generador ─────────────────────────────────
_CIPS = {
    "abscisa": "abscisa_val", "fecha": "fecha",
    "on_mv": "on_mv", "off_mv": "off_mv",
    "on_limpio": "on_limpio", "off_limpio": "off_limpio",
    "natural_mv": "natural_mv", "polarizacion_mv": "polarizacion_mv",
    "vac_mv": "vac_mv", "metal_on": "metal_on", "metal_off": "metal_off",
    "lejano_on": "far_on", "lejano_off": "far_off",
    "cercano_on": "near_on", "cercano_off": "near_off",
    "ir_on_off": "ir_on_off", "lat": "lat", "lon": "lon",
    "observaciones": "observaciones",
}


def _mapear(filas, mapa):
    """Traduce filas de la BD a dicts del generador, omitiendo los None que la
    BD rellenó y toda columna que no esté en el mapa (ids, derivados)."""
    salida = []
    for f in filas or []:
        d = {}
        for col, clave in mapa.items():
            v = f.get(col)
            if v is not None:
                d[clave] = v
        salida.append(d)
    return salida


def cips_desde_filas(filas):
    """`puntos_cips` → dicts de `data['cips']`."""
    return _mapear(filas, _CIPS)
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_revision_roundtrip.py -q
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
P="/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"; cp "$P/revision.py" /private/tmp/tgi_push/ && cp "$P/tests/test_revision_roundtrip.py" /private/tmp/tgi_push/tests/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(revision): mapeador inverso CIPS con round-trip"
```

---

### Task 4: `revision.py` — mapeadores PAP, DCVG y hallazgos

**Files:**
- Modify: `revision.py`
- Modify: `tests/test_revision_roundtrip.py`

- [ ] **Step 1: Escribir los tests que fallan**

Añade al final de `tests/test_revision_roundtrip.py`:

```python
PAP_ORIG = [{
    "abscisa": 800, "fecha": "2026-03-05", "on_mv": -1400.0, "off_mv": -880.0,
    "potencial_natural": -550.0, "polarizacion": -330.0, "vac": 1.8,
    "ir_on_off": 520.0, "resistencia": 12.0, "lat": 4.2, "lon": -75.3,
    "ref_geografica": "poste K0+800", "observaciones": "tapa suelta",
}]

POSTES_ORIG = [{
    "pk_m": 0, "tipo": "Poste", "on": -1500.0, "off": -1300.0, "vac": 2.0,
    "resistencia": 8.0, "lat": 4.0, "lon": -75.0,
}, {
    "pk_m": 100, "tipo": "Poste", "on": -1600.0, "off": -1200.0, "vac": 2.1,
    "resistencia": 9.0, "lat": 4.01, "lon": -75.01,
}]

DEFECTOS_ORIG = [{
    "pk_m": 50, "sector": "A", "forma_n": 12.0, "forma_e": 3.0,
    "forma_s": 6.0, "forma_o": 9.0, "caracter": "AA", "ol_re": 60.0,
    "profundidad": 1.2, "posicion_reloj": "6", "lat": 4.005, "lon": -75.005,
    "comentarios": "defecto en soldadura",
}]

RESIST_ORIG = [{
    "pk_m": 300, "sector": "B", "profundidad": 1.0,
    "r1": 10.0, "r2": 20.0, "r3": 30.0, "lat": 4.02, "lon": -75.02,
}]

HALLAZGOS_ORIG = [{
    "abscisa_val": 1500, "abscisa_fin": 1700, "longitud": 200.0,
    "lat": 4.03, "lon": -75.03, "lat_fin": 4.04, "lon_fin": -75.04,
    "fecha": "2026-03-06", "tipo": "Cruce", "descripcion": "cruce de vía",
}]


def test_pap_round_trip():
    vuelta = revision.pap_desde_filas(db._puntos_pap_filas("i", PAP_ORIG))
    for k, v in PAP_ORIG[0].items():
        assert vuelta[0][k] == v, f"se perdio o cambio '{k}'"


def test_postes_round_trip():
    vuelta = revision.postes_desde_filas(db._postes_dcvg_filas("i", POSTES_ORIG))
    for k, v in POSTES_ORIG[0].items():
        assert vuelta[0][k] == v, f"se perdio o cambio '{k}'"


def test_defectos_round_trip_sin_derivados():
    sev = db._severidad_dcvg(POSTES_ORIG, DEFECTOS_ORIG)
    filas = db._defectos_dcvg_filas("i", DEFECTOS_ORIG, sev)
    assert filas[0]["severidad_pct"] is not None       # la BD sí los guarda
    vuelta = revision.defectos_desde_filas(filas)
    for k, v in DEFECTOS_ORIG[0].items():
        assert vuelta[0][k] == v, f"se perdio o cambio '{k}'"
    for derivado in ("p_re", "severidad_pct", "clasificacion"):
        assert derivado not in vuelta[0], f"'{derivado}' es derivado, no se rehidrata"


def test_resistividades_round_trip():
    vuelta = revision.resist_desde_filas(db._resist_dcvg_filas("i", RESIST_ORIG))
    for k, v in RESIST_ORIG[0].items():
        assert vuelta[0][k] == v, f"se perdio o cambio '{k}'"


def test_hallazgos_round_trip():
    vuelta = revision.hallazgos_desde_filas(db._hallazgos_filas("i", HALLAZGOS_ORIG))
    for k, v in HALLAZGOS_ORIG[0].items():
        assert vuelta[0][k] == v, f"se perdio o cambio '{k}'"
```

- [ ] **Step 2: Correr los tests para verificar que fallan**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_revision_roundtrip.py -q
```

Expected: FAIL con `AttributeError: module 'revision' has no attribute 'pap_desde_filas'`.

- [ ] **Step 3: Añadir los mapas y funciones a `revision.py`**

Después de `_CIPS`, añade:

```python
_PAP = {
    "abscisa": "abscisa", "fecha": "fecha", "on_mv": "on_mv", "off_mv": "off_mv",
    "natural_mv": "potencial_natural", "polarizacion_mv": "polarizacion",
    "vac_mv": "vac", "ir_on_off": "ir_on_off", "resistencia": "resistencia",
    "lat": "lat", "lon": "lon", "ref_geografica": "ref_geografica",
    "observaciones": "observaciones",
}

_POSTES = {
    "abscisa": "pk_m", "tipo": "tipo", "on_mv": "on", "off_mv": "off",
    "vac_mv": "vac", "resistencia": "resistencia", "lat": "lat", "lon": "lon",
}

# p_re / severidad_pct / clasificacion NO están: los recalcula _severidad_dcvg.
_DEFECTOS = {
    "abscisa": "pk_m", "sector": "sector",
    "forma_n": "forma_n", "forma_e": "forma_e",
    "forma_s": "forma_s", "forma_o": "forma_o",
    "caracter": "caracter", "ol_re": "ol_re", "profundidad": "profundidad",
    "posicion_reloj": "posicion_reloj", "lat": "lat", "lon": "lon",
    "comentarios": "comentarios",
}

_RESIST = {
    "abscisa": "pk_m", "sector": "sector", "profundidad": "profundidad",
    "r1": "r1", "r2": "r2", "r3": "r3", "lat": "lat", "lon": "lon",
}

_HALLAZGOS = {
    "abscisa_ini": "abscisa_val", "abscisa_fin": "abscisa_fin",
    "longitud_m": "longitud", "lat_ini": "lat", "lon_ini": "lon",
    "lat_fin": "lat_fin", "lon_fin": "lon_fin",
    "fecha": "fecha", "tipo": "tipo", "descripcion": "descripcion",
}
```

Y después de `cips_desde_filas`:

```python
def pap_desde_filas(filas):
    """`puntos_pap` → dicts de `data['potenciales']`."""
    return _mapear(filas, _PAP)


def postes_desde_filas(filas):
    """`postes_dcvg` → dicts de `data['dcvg_postes']`."""
    return _mapear(filas, _POSTES)


def defectos_desde_filas(filas):
    """`defectos_dcvg` → dicts de `data['dcvg_defectos']` (sin derivados)."""
    return _mapear(filas, _DEFECTOS)


def resist_desde_filas(filas):
    """`resistividades_dcvg` → dicts de `data['dcvg_resist']`."""
    return _mapear(filas, _RESIST)


def hallazgos_desde_filas(filas):
    """`hallazgos` → dicts de `data['hallazgos']` / `data['dcvg_hallazgos']`."""
    return _mapear(filas, _HALLAZGOS)
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_revision_roundtrip.py -q
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
P="/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"; cp "$P/revision.py" /private/tmp/tgi_push/ && cp "$P/tests/test_revision_roundtrip.py" /private/tmp/tgi_push/tests/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(revision): mapeadores inversos PAP DCVG y hallazgos"
```

---

### Task 5: `revision.py` — categorías de observación y enrutamiento

**Files:**
- Modify: `revision.py`
- Create: `tests/test_revision_observaciones.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Categorías de rechazo y a dónde enruta cada una."""
import pytest

import revision


def test_categorias_son_las_cuatro_acordadas():
    assert set(revision.CATEGORIAS) == {
        "datos_generales", "procesamiento", "texto_campo", "falta_info"}


def test_etiqueta_legible_de_cada_categoria():
    for cat in revision.CATEGORIAS:
        assert revision.etiqueta(cat)
        assert revision.etiqueta(cat) != cat        # es legible, no el slug


def test_normalizar_acepta_dict_parcial():
    obs = revision.normalizar({"categoria": "texto_campo", "nota": "  ilegible "})
    assert obs["categoria"] == "texto_campo"
    assert obs["nota"] == "ilegible"
    assert obs["estado"] == "abierta" and obs["origen"] == "revisor"
    assert obs["abscisa_ini"] is None and obs["campo"] is None


def test_normalizar_rechaza_categoria_invalida():
    with pytest.raises(ValueError):
        revision.normalizar({"categoria": "lo_que_sea", "nota": "x"})


def test_normalizar_convierte_abscisas_a_entero():
    obs = revision.normalizar({"categoria": "procesamiento",
                               "abscisa_ini": "1200.6", "abscisa_fin": ""})
    assert obs["abscisa_ini"] == 1201 and obs["abscisa_fin"] is None


def test_requiere_crudos_solo_para_procesamiento():
    assert revision.requiere_crudos([{"categoria": "procesamiento"}]) is True
    assert revision.requiere_crudos([{"categoria": "texto_campo"},
                                     {"categoria": "datos_generales"}]) is False


def test_falta_info_no_vuelve_al_generador():
    assert revision.es_para_tecnico({"categoria": "falta_info"}) is True
    assert revision.es_para_tecnico({"categoria": "texto_campo"}) is False
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_revision_observaciones.py -q
```

Expected: FAIL con `AttributeError: module 'revision' has no attribute 'CATEGORIAS'`.

- [ ] **Step 3: Añadir el modelo al inicio de `revision.py`**

Justo después del docstring y del `from __future__ import annotations`:

```python
# ── Categorías de rechazo ───────────────────────────────────────────────────
# Cada una termina en un sitio distinto: por eso el rechazo se clasifica en vez
# de ser un párrafo suelto.
CATEGORIAS = ("datos_generales", "procesamiento", "texto_campo", "falta_info")

_ETIQUETAS = {
    "datos_generales": "Datos Generales (tramo, OT, contrato, fechas)",
    "procesamiento": "Procesamiento (abscisa, tramo, picos, clasificación)",
    "texto_campo": "Texto de campo (comentarios, hallazgos, conclusiones)",
    "falta_info": "Falta información (la debe subir el técnico)",
}


def etiqueta(categoria):
    """Nombre legible de una categoría, para la UI."""
    return _ETIQUETAS.get(categoria, categoria)


def _entero(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def normalizar(obs):
    """Completa y valida una observación venga de donde venga (formulario del
    revisor, `st.data_editor` o la IA). Lanza ValueError si la categoría no es
    una de las cuatro: es la única forma de enrutar bien la devolución."""
    cat = str(obs.get("categoria") or "").strip()
    if cat not in CATEGORIAS:
        raise ValueError(
            f"Categoría '{cat}' inválida. Debe ser una de: {', '.join(CATEGORIAS)}")
    return {
        "categoria": cat,
        "campo": (str(obs["campo"]).strip() or None) if obs.get("campo") else None,
        "abscisa_ini": _entero(obs.get("abscisa_ini")),
        "abscisa_fin": _entero(obs.get("abscisa_fin")),
        "nota": (str(obs.get("nota") or "").strip() or None),
        "origen": obs.get("origen") or "revisor",
        "estado": obs.get("estado") or "abierta",
    }


def requiere_crudos(observaciones):
    """¿Alguna observación obliga a reprocesar desde los archivos del técnico?
    Solo 'procesamiento': lo demás se arregla con la data ya publicada."""
    return any(o.get("categoria") == "procesamiento" for o in observaciones or [])


def es_para_tecnico(obs):
    """'falta_info' no abre el buzón: no hay nada que corregir en el generador,
    falta un archivo que solo el técnico puede subir."""
    return obs.get("categoria") == "falta_info"
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_revision_observaciones.py -q
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
P="/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"; cp "$P/revision.py" /private/tmp/tgi_push/ && cp "$P/tests/test_revision_observaciones.py" /private/tmp/tgi_push/tests/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(revision): categorias de rechazo y enrutamiento"
```

---

### Task 6: `db.py` — trazabilidad de origen y republicación en sitio

**Files:**
- Modify: `db.py` (`_fila_inspeccion` en la línea 321; las tres `guardar_inspeccion_*`)
- Create: `tests/test_db_revision.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""La fila de inspección recuerda de dónde salió y en qué revisión va."""
import pytest

import db


def test_fila_inspeccion_guarda_origen_y_revision():
    fila = db._fila_inspeccion(
        {"tramo": "Ansermanuevo", "ot": "OT-1"}, "CIPS", 0, 1000, {}, "PCC",
        carga_id="carga-123", contexto={"info": {"tramo": "Ansermanuevo"}},
        revision="B")
    assert fila["carga_id"] == "carga-123"
    assert fila["contexto"]["info"]["tramo"] == "Ansermanuevo"
    assert fila["revision"] == "B"


def test_fila_inspeccion_sin_origen_no_mete_claves_vacias():
    fila = db._fila_inspeccion({"tramo": "X"}, "CIPS", 0, 1, {}, "PCC")
    assert "carga_id" not in fila and "contexto" not in fila
    assert fila["revision"] == "A"


def test_reemplazar_devuelve_estado_a_revision_y_limpia_el_rechazo():
    fila = db._fila_inspeccion({"tramo": "X"}, "CIPS", 0, 1, {}, "PCC",
                               revision="B", reemplaza=True)
    assert fila["estado"] == "en_revision"
    assert fila["nota_revision"] is None
    assert fila["revisado_por"] is None and fila["revisado_en"] is None


def test_guardar_con_reemplaza_id_sin_config_lanza_error(monkeypatch):
    monkeypatch.setattr(db, "_secrets", lambda: {})
    with pytest.raises(RuntimeError):
        db.guardar_inspeccion_cips({}, [], [], reemplaza_id="insp-1")
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_db_revision.py -q
```

Expected: FAIL con `TypeError: _fila_inspeccion() got an unexpected keyword argument 'carga_id'`.

- [ ] **Step 3: Ampliar `_fila_inspeccion` (db.py:321)**

```python
def _fila_inspeccion(info, tipo, abscisa_ini, abscisa_fin, resumen, creado_por,
                     carga_id=None, contexto=None, revision="A", reemplaza=False):
    """Fila de `inspecciones`. `carga_id` y `contexto` son la trazabilidad que
    permite reabrir el informe en el generador si lo rechazan; `reemplaza`
    devuelve la inspección a revisión al republicar una corrección."""
    fila = {
        "tipo": tipo,
        "gasoducto": info.get("gasoducto"), "tramo": info.get("tramo"),
        "fecha": _fecha(info.get("fecha")), "inspector": info.get("inspector"),
        "ciclo": str(info.get("ciclo") or info.get("cycle") or "") or None,
        "ot": info.get("ot"), "contratista": info.get("contratista"),
        "serial_equipo": info.get("serial_equipo"),
        "tipo_recubrimiento": info.get("tipo_recubrimiento"),
        "diametro": str(info.get("diametro") or "") or None,
        "abscisa_ini": abscisa_ini, "abscisa_fin": abscisa_fin,
        "resumen": resumen, "creado_por": creado_por,
        "revision": revision or "A",
    }
    if carga_id:
        fila["carga_id"] = carga_id
    if contexto:
        fila["contexto"] = contexto
    if reemplaza:
        # Una corrección republicada vuelve a la cola del revisor limpia.
        fila["estado"] = "en_revision"
        fila["nota_revision"] = None
        fila["revisado_por"] = None
        fila["revisado_en"] = None
    return fila
```

- [ ] **Step 4: Añadir el helper de insertar-o-reemplazar justo debajo**

```python
_HIJAS = {
    "CIPS": ("puntos_cips", "hallazgos", "tramos_no_inspeccionados"),
    "PAP": ("puntos_pap", "hallazgos"),
    "DCVG": ("postes_dcvg", "defectos_dcvg", "resistividades_dcvg", "hallazgos"),
}


def _crear_o_reemplazar(cli, fila, tipo, reemplaza_id=None):
    """Inserta una inspección nueva, o —si es una corrección— actualiza la fila
    existente y borra sus filas hijas para que se reescriban. Actualizar en
    sitio evita que el portal acumule un duplicado por cada revisión."""
    if not reemplaza_id:
        return cli.table("inspecciones").insert(fila).execute().data[0]["id"]
    cli.table("inspecciones").update(fila).eq("id", reemplaza_id).execute()
    for tabla in _HIJAS.get(tipo, ()):
        cli.table(tabla).delete().eq("inspeccion_id", reemplaza_id).execute()
    return reemplaza_id
```

- [ ] **Step 5: Cablear los tres `guardar_inspeccion_*`**

En `guardar_inspeccion_cips`, cambia la firma a:

```python
def guardar_inspeccion_cips(info: dict, cips: list, hallazgos: list,
                            tramos: list | None = None,
                            excel_bytes: bytes | None = None,
                            excel_nombre: str | None = None,
                            ppm_bytes: bytes | None = None,
                            ppm_nombre: str | None = None,
                            creado_por: str = "PCC",
                            carga_id: str | None = None,
                            contexto: dict | None = None,
                            revision: str = "A",
                            reemplaza_id: str | None = None) -> str:
```

y reemplaza el `res = cli.table("inspecciones").insert(fila).execute()` +
`insp_id = res.data[0]["id"]` por:

```python
    insp_id = _crear_o_reemplazar(
        cli,
        _fila_inspeccion(info, "CIPS", abscisa_ini, abscisa_fin, resumen,
                         creado_por, carga_id, contexto, revision,
                         reemplaza=bool(reemplaza_id)),
        "CIPS", reemplaza_id)
```

(la variable `fila` que se construía a mano en `guardar_inspeccion_cips` ya no
se usa: bórrala.)

En `guardar_inspeccion_pap` añade los mismos cuatro parámetros al final de la
firma y cambia:

```python
    insp_id = _crear_o_reemplazar(
        cli,
        _fila_inspeccion(info, "PAP", a_ini, a_fin, resumen, creado_por,
                         carga_id, contexto, revision,
                         reemplaza=bool(reemplaza_id)),
        "PAP", reemplaza_id)
```

En `guardar_inspeccion_dcvg`, igual:

```python
    insp_id = _crear_o_reemplazar(
        cli,
        _fila_inspeccion(info, "DCVG", a_ini, a_fin, resumen, creado_por,
                         carga_id, contexto, revision,
                         reemplaza=bool(reemplaza_id)),
        "DCVG", reemplaza_id)
```

- [ ] **Step 6: Correr los tests para verificar que pasan**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_db_revision.py tests/test_db.py -q
```

Expected: todos passed (4 nuevos + los de `test_db.py`).

- [ ] **Step 7: Commit**

```bash
P="/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"; cp "$P/db.py" /private/tmp/tgi_push/ && cp "$P/tests/test_db_revision.py" /private/tmp/tgi_push/tests/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(db): trazabilidad de origen y republicacion en sitio"
```

---

### Task 7: `db.py` — CRUD de observaciones de revisión

**Files:**
- Modify: `db.py` (`rechazar_inspeccion` en la línea 272)
- Modify: `tests/test_db_revision.py`

- [ ] **Step 1: Escribir el test que falla**

Añade al final de `tests/test_db_revision.py`:

```python
def test_obs_filas_normaliza_y_ata_a_la_inspeccion():
    filas = db._obs_filas("insp-9", [
        {"categoria": "texto_campo", "nota": " comentarios ilegibles ",
         "abscisa_ini": "12000", "abscisa_fin": "15000"},
        {"categoria": "datos_generales", "campo": "info.tramo",
         "nota": "dice Cartago, es Ansermanuevo"},
    ])
    assert len(filas) == 2
    assert all(f["inspeccion_id"] == "insp-9" for f in filas)
    assert filas[0]["nota"] == "comentarios ilegibles"
    assert filas[0]["abscisa_ini"] == 12000
    assert filas[1]["campo"] == "info.tramo"
    assert all(f["estado"] == "abierta" for f in filas)


def test_obs_filas_propaga_el_error_de_categoria_invalida():
    with pytest.raises(ValueError):
        db._obs_filas("insp-9", [{"categoria": "inventada", "nota": "x"}])


def test_rechazar_sin_config_lanza_error(monkeypatch):
    monkeypatch.setattr(db, "_secrets", lambda: {})
    with pytest.raises(RuntimeError):
        db.rechazar_inspeccion("insp-1", observaciones=[
            {"categoria": "texto_campo", "nota": "x"}])
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_db_revision.py -q
```

Expected: FAIL con `AttributeError: module 'db' has no attribute '_obs_filas'`.

- [ ] **Step 3: Reemplazar `rechazar_inspeccion` y añadir el resto (db.py:272)**

```python
def _obs_filas(insp_id, observaciones):
    """Normaliza y ata a la inspección las observaciones de un rechazo.
    Pura: `revision.normalizar` valida la categoría y lanza ValueError."""
    import revision
    return [dict(revision.normalizar(o), inspeccion_id=insp_id)
            for o in (observaciones or [])]


def rechazar_inspeccion(insp_id: str, revisor: str = "PCC", nota: str = "",
                        observaciones: list | None = None):
    """Rechaza una inspección. `observaciones` es la lista estructurada que el
    generador usa para enrutar la corrección; `nota` queda como resumen legible
    (es lo que el portal ya mostraba)."""
    filas = _obs_filas(insp_id, observaciones)      # valida ANTES de escribir
    cli = _client(write=True)
    if not nota and filas:
        import revision
        nota = " · ".join(
            f"{revision.etiqueta(f['categoria'])}: {f['nota'] or ''}".strip(" :")
            for f in filas)
    cli.table("inspecciones").update(
        {"estado": "rechazada", "revisado_por": revisor,
         "revisado_en": _dt.datetime.utcnow().isoformat(),
         "nota_revision": nota or None}
    ).eq("id", insp_id).execute()
    if filas:
        _insert_lotes(cli, "observaciones_revision", filas)


def observaciones_de(insp_id: str, estado: str | None = "abierta") -> list[dict]:
    """Observaciones de un rechazo, las más viejas primero."""
    q = (_client(write=True).table("observaciones_revision").select("*")
         .eq("inspeccion_id", insp_id).order("creado_en"))
    if estado:
        q = q.eq("estado", estado)
    return q.execute().data or []


def listar_rechazadas(tipo: str | None = None) -> list[dict]:
    """Inspecciones rechazadas pendientes de corregir (buzón del generador)."""
    q = (_client(write=True).table("inspecciones")
         .select("id, tipo, tramo, fecha, inspector, ot, revision, "
                 "nota_revision, revisado_en, carga_id, contexto, excel_path")
         .eq("estado", "rechazada").order("revisado_en", desc=True))
    if tipo:
        q = q.eq("tipo", tipo)
    return q.execute().data or []


def marcar_observaciones(insp_id: str, estado: str = "resuelta"):
    """Cierra las observaciones abiertas de una inspección ya corregida."""
    _client(write=True).table("observaciones_revision").update(
        {"estado": estado}).eq("inspeccion_id", insp_id).eq(
        "estado", "abierta").execute()
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_db_revision.py -q
```

Expected: 7 passed.

- [ ] **Step 5: Verificar contra Supabase de verdad**

Run (usa una inspección real; el script elige la primera que encuentre y
deshace lo que hizo):

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -c "
import tomllib, db
with open('.streamlit/secrets.toml','rb') as f: s = tomllib.load(f)
db._secrets = lambda: s['supabase']
cli = db._client(write=True)
ins = cli.table('inspecciones').select('id,estado').limit(1).execute().data
assert ins, 'no hay inspecciones para probar'
iid, antes = ins[0]['id'], ins[0]['estado']
db.rechazar_inspeccion(iid, nota='', observaciones=[
    {'categoria':'texto_campo','nota':'PRUEBA borrar','abscisa_ini':1000}])
print('observaciones:', db.observaciones_de(iid))
print('en el buzon:', [r['id'] for r in db.listar_rechazadas()])
db.marcar_observaciones(iid)
cli.table('observaciones_revision').delete().eq('inspeccion_id', iid).execute()
cli.table('inspecciones').update({'estado':antes,'nota_revision':None}).eq('id',iid).execute()
print('limpio, estado restaurado a', antes)
"
```

Expected: imprime una observación con `categoria: texto_campo`, la inspección
aparece en el buzón, y termina en `limpio, estado restaurado a ...`.

- [ ] **Step 6: Commit**

```bash
P="/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"; cp "$P/db.py" /private/tmp/tgi_push/ && cp "$P/tests/test_db_revision.py" /private/tmp/tgi_push/tests/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(db): CRUD de observaciones de revision y buzon de rechazadas"
```

---

### Task 8: `nombres.py` — revisión en el nombre del entregable

**Files:**
- Modify: `nombres.py:180-200`
- Create: `tests/test_nombres_revision.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""El entregable corregido no puede llamarse Rev.A igual que el rechazado."""
import nombres


INFO = {"tipo_inspeccion": "DCVG", "tramo": "Salento", "fecha": "2026-03-15",
        "ot": "1300013506", "contrato": "551007370", "tipo_ducto": "Ramal"}


def test_por_defecto_sigue_siendo_rev_a():
    assert nombres.nombre_archivo(INFO).endswith("_PCC_Rev.A.xlsx")


def test_revision_b_cambia_el_sufijo():
    assert nombres.nombre_archivo(INFO, revision="B").endswith("_PCC_Rev.B.xlsx")


def test_el_resto_del_nombre_no_cambia():
    a = nombres.nombre_archivo(INFO)
    b = nombres.nombre_archivo(INFO, revision="B")
    assert a.replace("Rev.A", "Rev.B") == b


def test_siguiente_revision_avanza_la_letra():
    assert nombres.siguiente_revision("A") == "B"
    assert nombres.siguiente_revision("B") == "C"
    assert nombres.siguiente_revision(None) == "B"    # sin dato: ya hubo una
    assert nombres.siguiente_revision("Z") == "Z"     # tope, no da la vuelta
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_nombres_revision.py -q
```

Expected: FAIL con `TypeError: nombre_archivo() got an unexpected keyword argument 'revision'`.

- [ ] **Step 3: Modificar `nombres.py`**

Cambia la firma y la última parte (`nombres.py:180` y `:198`):

```python
def nombre_archivo(info, doc="REP", ext=".xlsx", revision="A"):
    """Nombre codificado del entregable. `doc` = 'REP' (informe) o 'PPM'.
    `revision` sube a 'B', 'C'... cuando se republica una corrección."""
```

y en la lista `partes`, reemplaza `"Rev.A",` por:

```python
        f"Rev.{(revision or 'A').strip().upper()}",
```

Añade al final del módulo:

```python
def siguiente_revision(actual):
    """Letra que sigue. Sin dato asume que la publicada era la A. En 'Z' se
    queda quieta: 26 correcciones del mismo informe es otro problema."""
    letra = (str(actual or "A").strip().upper() or "A")[:1]
    if not letra.isalpha() or letra >= "Z":
        return "Z" if letra == "Z" else "B"
    return chr(ord(letra) + 1)
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_nombres_revision.py tests/ -q -k "nombre or nombres" 
```

Expected: 4 passed y ningún test de nombres existente roto.

- [ ] **Step 5: Commit**

```bash
P="/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"; cp "$P/nombres.py" /private/tmp/tgi_push/ && cp "$P/tests/test_nombres_revision.py" /private/tmp/tgi_push/tests/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(nombres): revision en el nombre del entregable"
```

---

### Task 9: `portal_app.py` — rechazo estructurado

**Files:**
- Modify: `portal_app.py:326-336` (el `popover` de rechazo dentro de `_barra_revision`)

- [ ] **Step 1: Reemplazar el popover de rechazo**

Sustituye el bloque que hoy es:

```python
        with cb.popover("✋ Rechazar"):
            _nota = st.text_input("Motivo del rechazo", key=f"nota_{insp['id']}")
            if st.button("Confirmar rechazo", key=f"rej_{insp['id']}"):
                db.rechazar_inspeccion(insp["id"], revisor="PCC", nota=_nota)
                _refrescar()
                st.session_state.sel = None
                st.session_state.sel_tipo = None
                st.rerun()
```

por:

```python
        with cb.popover("✋ Rechazar"):
            import revision as _rev
            st.caption("Marca **qué** está mal y **dónde**. El generador usa esto "
                       "para abrir el informe en el punto exacto.")
            _obs = st.data_editor(
                [{"categoria": "datos_generales", "campo": "", "abscisa_ini": None,
                  "abscisa_fin": None, "nota": ""}],
                key=f"obs_{insp['id']}", num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "categoria": st.column_config.SelectboxColumn(
                        "Qué está mal", options=list(_rev.CATEGORIAS),
                        required=True, width="medium"),
                    "campo": st.column_config.TextColumn(
                        "Campo", help="Opcional: 'info.tramo', 'hallazgo.descripcion'"),
                    "abscisa_ini": st.column_config.NumberColumn("Abscisa desde (m)"),
                    "abscisa_fin": st.column_config.NumberColumn("Abscisa hasta (m)"),
                    "nota": st.column_config.TextColumn("Qué hay que corregir",
                                                        width="large"),
                })
            st.caption(" · ".join(f"**{c}**: {_rev.etiqueta(c)}"
                                  for c in _rev.CATEGORIAS))
            if st.button("Confirmar rechazo", key=f"rej_{insp['id']}"):
                _lista = [o for o in _obs if (o.get("nota") or "").strip()]
                if not _lista:
                    st.warning("Escribe al menos una observación con su nota.")
                else:
                    try:
                        db.rechazar_inspeccion(insp["id"], revisor="PCC",
                                               observaciones=_lista)
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        _refrescar()
                        st.session_state.sel = None
                        st.session_state.sel_tipo = None
                        st.rerun()
```

- [ ] **Step 2: Mostrar las observaciones en el estado "rechazada"**

Sustituye el bloque `elif estado == "rechazada":` por:

```python
    elif estado == "rechazada":
        try:
            _obs_ab = db.observaciones_de(insp["id"])
        except Exception:
            _obs_ab = []
        if _obs_ab:
            import revision as _rev
            st.markdown("**Pendiente de corregir en el generador:**")
            for _o in _obs_ab:
                _donde = ""
                if _o.get("abscisa_ini") is not None:
                    _donde = f" · {_abscisa_txt(_o['abscisa_ini'])}"
                    if _o.get("abscisa_fin") is not None:
                        _donde += f" a {_abscisa_txt(_o['abscisa_fin'])}"
                st.caption(f"· *{_rev.etiqueta(_o['categoria'])}*{_donde} — "
                           f"{_o.get('nota') or ''}")
        if st.button("↩️ Reabrir para revisión", key=f"reab_{insp['id']}"):
            _client_reabrir(insp["id"])
            _refrescar()
            st.rerun()
```

- [ ] **Step 3: Verificar en el portal local**

Abre el portal con el navegador de la herramienta (`preview_start` con la
entrada de `launch.json`, puerto 8602), entra como **revisor**, abre una
inspección en revisión y despliega "✋ Rechazar".

Expected: se ve la tabla editable con el selector de categoría (4 opciones), se
pueden añadir filas con el `+`, y "Confirmar rechazo" sin nota muestra el aviso
amarillo en vez de rechazar.

- [ ] **Step 4: Rechazar de verdad y comprobar el ciclo**

Rechaza esa inspección con dos observaciones (una `texto_campo` con abscisas y
una `datos_generales` con campo `info.tramo`). Vuelve a abrirla.

Expected: aparece "Pendiente de corregir en el generador:" con las dos líneas y
sus abscisas en formato `K 012+000`. Déjala rechazada: la Tarea 11 la usa.

- [ ] **Step 5: Commit**

```bash
cp "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente/portal_app.py" /private/tmp/tgi_push/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(portal): rechazo estructurado por categoria y abscisa"
```

---

### Task 10: `streamlit_app.py` — guardar el origen al publicar

**Files:**
- Modify: `streamlit_app.py:399` (`autocargar_carga`) y `:1566-1595` (bloque de publicar)

- [ ] **Step 1: Recordar la carga que se trajo**

En `autocargar_carga(cg)`, justo después de `msgs, avisos = [], []`, añade:

```python
    # De qué carga salió este informe: es lo que permite reprocesar los crudos
    # si el portal lo rechaza por un error de procesamiento.
    if cg.get("id"):
        st.session_state.setdefault("cargas_usadas", [])
        if cg["id"] not in st.session_state.cargas_usadas:
            st.session_state.cargas_usadas.append(cg["id"])
```

- [ ] **Step 2: Añadir el constructor de contexto a la zona de helpers**

Justo después de `_autollenar_tramo` (termina en la línea ~295, antes del
comentario `# ── App ───`) añade, a nivel de módulo:

```python
def _contexto_generacion(tipo):
    """Snapshot pequeño de con qué se generó el informe. Es lo que rehidrata
    Datos Generales al reabrirlo: la fila `inspecciones` solo guarda algunos
    campos (tramo, OT, inspector...), no el `info` completo."""
    return {
        "info": dict(data.get('info') or {}),
        "tipo": tipo,
        "informe_nombre": st.session_state.get("informe_nombre"),
        "cips": {k: st.session_state.get(k)
                 for k in ("cips_emp", "cips_dist", "cips_tr", "cips_tr_oc")
                 if st.session_state.get(k)},
    }
```

- [ ] **Step 3: Pasar origen y contexto en las tres llamadas**

Dentro del `elif st.button(f"Publicar {_tipo_pub} al portal", ...)`, justo
después de `_ppm_nombre = _nombre_ppm()`, añade:

```python
                    _cargas = st.session_state.get("cargas_usadas") or []
                    _origen = {"carga_id": _cargas[0] if _cargas else None,
                               "contexto": _contexto_generacion(_tipo_pub)}
```

y añade `**_origen` como último argumento de las tres llamadas. Quedan así:

```python
                        _id = db.guardar_inspeccion_cips(
                            _info, data['cips'], cips_a_hallazgos(data['cips']),
                            excel_bytes=st.session_state.informe_bytes,
                            excel_nombre=st.session_state.informe_nombre,
                            ppm_bytes=st.session_state.ppm_bytes,
                            ppm_nombre=_ppm_nombre, creado_por="PCC", **_origen)
```

```python
                        _id = db.guardar_inspeccion_dcvg(
                            _info, data['dcvg_postes'], data['dcvg_defectos'],
                            data['dcvg_resist'], cips_a_hallazgos(data['dcvg_hallazgos']),
                            excel_bytes=st.session_state.informe_bytes,
                            excel_nombre=st.session_state.informe_nombre,
                            creado_por="PCC", **_origen)
```

```python
                        _id = db.guardar_inspeccion_pap(
                            _info, data['potenciales'], data['hallazgos'],
                            excel_bytes=st.session_state.informe_bytes,
                            excel_nombre=st.session_state.informe_nombre,
                            ppm_bytes=st.session_state.ppm_bytes,
                            ppm_nombre=_ppm_nombre, creado_por="PCC", **_origen)
```

- [ ] **Step 4: Verificar publicando de verdad**

Levanta la app de procesamiento, trae una carga desde la bandeja, genera y
publica. Después:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -c "
import tomllib, db
with open('.streamlit/secrets.toml','rb') as f: s = tomllib.load(f)
db._secrets = lambda: s['supabase']
r = db._client(write=True).table('inspecciones').select(
    'id,tramo,revision,carga_id,contexto').order('creado_en', desc=True).limit(1).execute().data[0]
print('revision:', r['revision'], '| carga_id:', r['carga_id'])
print('info del contexto:', sorted((r.get('contexto') or {}).get('info', {}).keys()))
"
```

Expected: `revision: A`, un `carga_id` no nulo (si vino de la bandeja) y una
lista de claves de `info` que incluya `tramo`, `ot` y `contrato` — más campos
que los que guarda la fila.

- [ ] **Step 5: Commit**

```bash
cp "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente/streamlit_app.py" /private/tmp/tgi_push/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(app): guardar carga de origen y contexto al publicar"
```

---

### Task 11: `revision.rehidratar` + buzón de rechazos en el generador

**Files:**
- Modify: `revision.py`
- Modify: `tests/test_revision_roundtrip.py`
- Modify: `streamlit_app.py` (dentro del bloque `if db.disponible(write=True):` de la Bandeja de entrada, después del bucle de cargas por tramo)

- [ ] **Step 1: Escribir el test de `rehidratar` que falla**

Añade al final de `tests/test_revision_roundtrip.py`:

```python
DETALLE_CIPS = {
    "inspeccion": {
        "id": "insp-1", "tipo": "CIPS", "tramo": "Ansermanuevo",
        "fecha": "2026-03-04", "inspector": "Juan Perez", "ot": "OT-9",
        "contexto": {"info": {"tramo": "Ansermanuevo", "contrato": "551007370",
                              "tipo_ducto": "Ramal", "distrito": "7"}},
    },
    "puntos": [], "hallazgos": [], "tramos": [],
}


def test_rehidratar_prefiere_el_contexto_y_completa_con_la_fila():
    out = revision.rehidratar(DETALLE_CIPS, "CIPS")
    # del contexto (la fila `inspecciones` no guarda estos)
    assert out["info"]["contrato"] == "551007370"
    assert out["info"]["tipo_ducto"] == "Ramal"
    # de la fila (el contexto no los traía)
    assert out["info"]["inspector"] == "Juan Perez"
    assert out["info"]["ot"] == "OT-9"
    assert out["info"]["tipo_inspeccion"] == "CIPS"


def test_rehidratar_cips_devuelve_las_claves_del_tipo():
    detalle = dict(DETALLE_CIPS, puntos=db._puntos_cips_filas("i", CIPS_ORIG))
    out = revision.rehidratar(detalle, "CIPS")
    assert out["cips"][0]["abscisa_val"] == 1200
    assert "dcvg_postes" not in out and "potenciales" not in out


def test_rehidratar_dcvg_devuelve_las_cuatro_listas():
    sev = db._severidad_dcvg(POSTES_ORIG, DEFECTOS_ORIG)
    detalle = {
        "inspeccion": {"id": "i", "tipo": "DCVG", "tramo": "Salento"},
        "postes": db._postes_dcvg_filas("i", POSTES_ORIG),
        "defectos": db._defectos_dcvg_filas("i", DEFECTOS_ORIG, sev),
        "resistividades": db._resist_dcvg_filas("i", RESIST_ORIG),
        "hallazgos": db._hallazgos_filas("i", HALLAZGOS_ORIG),
    }
    out = revision.rehidratar(detalle, "DCVG")
    assert out["dcvg_postes"][0]["pk_m"] == 0
    assert out["dcvg_defectos"][0]["ol_re"] == 60.0
    assert out["dcvg_resist"][0]["r2"] == 20.0
    assert out["dcvg_hallazgos"][0]["descripcion"] == "cruce de vía"
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_revision_roundtrip.py -q
```

Expected: FAIL con `AttributeError: module 'revision' has no attribute 'rehidratar'`.

- [ ] **Step 3: Añadir `rehidratar` al final de `revision.py`**

```python
# Campos de `info` que la fila `inspecciones` sí guarda, por si no hay contexto
# (informes publicados antes del esquema v9).
_INFO_DE_FILA = ("gasoducto", "tramo", "fecha", "inspector", "ciclo", "ot",
                 "contratista", "serial_equipo", "tipo_recubrimiento", "diametro")


def rehidratar(detalle, tipo):
    """Detalle de `db.cargar_inspeccion_*` → dicts listos para `data`.

    `info` sale del `contexto` snapshoteado al publicar (es el completo) y se
    completa con las columnas de la fila cuando falte algo. Devuelve solo las
    claves del tipo, para no pisar listas de otros tipos en la sesión.
    """
    insp = (detalle or {}).get("inspeccion") or {}
    info = dict((insp.get("contexto") or {}).get("info") or {})
    for col in _INFO_DE_FILA:
        if not info.get(col) and insp.get(col):
            info[col] = insp[col]
    info["tipo_inspeccion"] = insp.get("tipo") or tipo

    out = {"info": info}
    if tipo == "CIPS":
        out["cips"] = cips_desde_filas(detalle.get("puntos"))
        out["hallazgos"] = hallazgos_desde_filas(detalle.get("hallazgos"))
    elif tipo == "PAP":
        out["potenciales"] = pap_desde_filas(detalle.get("puntos"))
        out["hallazgos"] = hallazgos_desde_filas(detalle.get("hallazgos"))
    else:
        out["dcvg_postes"] = postes_desde_filas(detalle.get("postes"))
        out["dcvg_defectos"] = defectos_desde_filas(detalle.get("defectos"))
        out["dcvg_resist"] = resist_desde_filas(detalle.get("resistividades"))
        out["dcvg_hallazgos"] = hallazgos_desde_filas(detalle.get("hallazgos"))
    return out
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_revision_roundtrip.py -q
```

Expected: 10 passed.

- [ ] **Step 5: Añadir el buzón a la Bandeja de entrada**

En `streamlit_app.py`, dentro del `if db.disponible(write=True):` de la Bandeja
de entrada y **después** del `for _gk, _lista in _grupos.items():` (es decir,
cuando termina el bloque de cargas por tramo), añade:

```python
        # — Rechazos por corregir ————————————————————————————————————
        # Un informe rechazado en el portal vuelve aquí con sus observaciones.
        # Se rehidrata de las filas ya publicadas: no hace falta el crudo salvo
        # que el problema sea de procesamiento.
        import revision as _rev

        @st.cache_data(ttl=45, show_spinner=False)
        def _rechazos_datos():
            try:
                return db.listar_rechazadas(), None
            except Exception as e:
                return [], str(e)

        _rech, _err_rech = _rechazos_datos()
        if _err_rech:
            st.caption(f"⚠️ rechazos: {_err_rech}")
        if _rech:
            tema.seccion(st, f"🔧 Rechazos por corregir · {len(_rech)}")
        for _r in _rech:
            _ico = _ICONO_TIPO.get(_r.get("tipo"), "📄")
            with st.expander(
                    f"{_ico} **{_r.get('tramo') or '—'}** · {_r.get('tipo')} · "
                    f"Rev.{_r.get('revision') or 'A'} · OT {_r.get('ot') or '—'}",
                    expanded=False):
                try:
                    _obs = db.observaciones_de(_r["id"])
                except Exception as _e:
                    _obs = []
                    st.caption(f"⚠️ no se pudieron leer las observaciones: {_e}")
                for _o in _obs:
                    _d = ""
                    if _o.get("abscisa_ini") is not None:
                        _d = f" · K {_o['abscisa_ini'] // 1000:03d}+{_o['abscisa_ini'] % 1000:03d}"
                    st.markdown(f"- **{_rev.etiqueta(_o['categoria'])}**{_d} — "
                                f"{_o.get('nota') or ''}")
                if not _obs and _r.get("nota_revision"):
                    st.markdown(f"- {_r['nota_revision']}")

                _para_tecnico = [_o for _o in _obs if _rev.es_para_tecnico(_o)]
                _corregibles = [_o for _o in _obs if not _rev.es_para_tecnico(_o)]

                _c1, _c2 = st.columns(2)
                if _corregibles or not _obs:
                    if _c1.button("🔧 Abrir para corregir", key=f"corr_{_r['id']}",
                                  type="primary", use_container_width=True):
                        with st.spinner("Rehidratando la inspección..."):
                            _tp = _r.get("tipo")
                            if _tp == "CIPS":
                                _det = db.cargar_inspeccion_cips(_r["id"], write=True)
                            elif _tp == "PAP":
                                _det = db.cargar_inspeccion_pap(_r["id"], write=True)
                            else:
                                _det = db.cargar_inspeccion_dcvg(_r["id"], write=True)
                            _reh = _rev.rehidratar(_det, _tp)
                            for _k, _v in _reh.items():
                                if _k != "info":
                                    data[_k] = _v
                            data["info"].update(_reh["info"])
                            # Los text_input con key SOLO se refrescan así.
                            st.session_state.pending_autofill = dict(
                                st.session_state.get("pending_autofill") or {},
                                **_reh["info"])
                            st.session_state.corrigiendo = {
                                "id": _r["id"], "tipo": _tp,
                                "revision": _r.get("revision") or "A"}
                            st.session_state.publicado_id = None
                            st.session_state.flash_autocarga = (
                                f"Informe de {_r.get('tramo')} abierto para corregir "
                                f"({len(_corregibles) or len(_obs)} observación(es)). "
                                f"Al republicar sube a Rev."
                                f"{nombres.siguiente_revision(_r.get('revision'))}.")
                        _rechazos_datos.clear()
                        st.rerun()
                if _r.get("carga_id") and _rev.requiere_crudos(_obs):
                    if _c2.button("📦 Reprocesar desde crudos",
                                  key=f"crudo_{_r['id']}", use_container_width=True,
                                  help="Vuelve a bajar los archivos del técnico y "
                                       "los pasa por los readers desde cero."):
                        with st.spinner("Bajando los crudos de la carga original..."):
                            _cg = (db._client(write=True).table("cargas").select("*")
                                   .eq("id", _r["carga_id"]).single().execute().data)
                            _m, _a = autocargar_carga(_cg)
                            st.session_state.corrigiendo = {
                                "id": _r["id"], "tipo": _r.get("tipo"),
                                "revision": _r.get("revision") or "A"}
                            st.session_state.publicado_id = None
                            st.session_state.flash_autocarga = (
                                "Crudos recargados: " + " · ".join(_m))
                        _rechazos_datos.clear()
                        st.rerun()
                elif _rev.requiere_crudos(_obs):
                    _c2.caption("⚠️ Hay un problema de procesamiento pero esta "
                                "inspección no guardó su carga de origen: sube los "
                                "crudos a mano en la pestaña de carga manual.")
                if _para_tecnico:
                    st.warning("Falta información que solo el técnico puede subir "
                               "— ver el botón de abajo.", icon=":material/person:")
```

- [ ] **Step 6: Verificar el buzón en la app**

Levanta la app de procesamiento y abre la pestaña "Archivos". La inspección que
rechazaste en la Tarea 9 debe aparecer bajo "🔧 Rechazos por corregir" con sus
dos observaciones.

Oprime "🔧 Abrir para corregir".

Expected: mensaje verde de que se abrió para corregir, y al ir a "Datos
Generales" los campos (Tramo, Contrato, OT, Contratista...) están llenos con los
valores del informe rechazado — no vacíos. En la pestaña del tipo
correspondiente, el contador "En memoria: N registros" muestra los puntos.

- [ ] **Step 7: Commit**

```bash
P="/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"; cp "$P/revision.py" "$P/streamlit_app.py" /private/tmp/tgi_push/ && cp "$P/tests/test_revision_roundtrip.py" /private/tmp/tgi_push/tests/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(app): buzon de rechazos y rehidratacion de la sesion"
```

---

### Task 12: Republicar la corrección como Rev.B

**Files:**
- Modify: `streamlit_app.py` (llamadas a `nombres.nombre_archivo` en 1357, 1370, 1464, 1468, 1476; bloque de publicar en ~1566)

- [ ] **Step 1: Añadir el helper de revisión actual**

Justo antes de `_contexto_generacion` (la que añadiste en la Tarea 10, en la
zona de helpers después de `_autollenar_tramo`):

```python
def _revision_actual():
    """Letra de revisión del entregable. Si se está corrigiendo un rechazo,
    sube a la siguiente para no entregar dos archivos llamados Rev.A."""
    _c = st.session_state.get("corrigiendo") or {}
    return nombres.siguiente_revision(_c.get("revision")) if _c else "A"
```

Las dos funciones usan el global `data`, que se asigna más abajo
(`data = st.session_state.data`): no importa, se resuelve al llamarlas, no al
definirlas.

- [ ] **Step 2: Pasar la revisión a los cinco nombres**

Cambia las cinco llamadas así:

```python
                nombre = nombres.nombre_archivo(info, revision=_revision_actual())
```

```python
                    ppm_nom = nombres.nombre_archivo(info, doc="PPM", revision=_revision_actual())
```

```python
            nombre = nombres.nombre_archivo(info, revision=_revision_actual())
```

```python
            ppm_path = os.path.join(tmpd, nombres.nombre_archivo(info, doc="PPM", revision=_revision_actual()))
```

```python
            st.session_state.ppm_nombre = nombres.nombre_archivo(info, doc="PPM", revision=_revision_actual())
```

- [ ] **Step 3: Avisar en la UI de publicar que es una corrección**

Justo después de `st.markdown(f"**Portal TGI** · publicar inspección {_tipo_pub}")`:

```python
            _corr = st.session_state.get("corrigiendo") or {}
            if _corr:
                st.info(f"Estás corrigiendo un informe rechazado. Al publicar se "
                        f"**actualiza la misma inspección** como "
                        f"Rev.{_revision_actual()} y vuelve a la cola del revisor.",
                        icon=":material/history:")
```

- [ ] **Step 4: Pasar `reemplaza_id` y `revision` al publicar**

Cambia el bloque `_origen` que añadiste en la Tarea 10 por:

```python
                    _cargas = st.session_state.get("cargas_usadas") or []
                    _corr = st.session_state.get("corrigiendo") or {}
                    _origen = {"carga_id": _cargas[0] if _cargas else None,
                               "contexto": _contexto_generacion(_tipo_pub),
                               "revision": _revision_actual(),
                               "reemplaza_id": _corr.get("id") or None}
```

- [ ] **Step 5: Cerrar las observaciones al publicar bien**

Reemplaza `st.session_state.publicado_id = _id` + `st.rerun()` por:

```python
                    if _corr.get("id"):
                        db.marcar_observaciones(_corr["id"], "resuelta")
                        st.session_state.corrigiendo = None
                    st.session_state.publicado_id = _id
                    st.rerun()
```

- [ ] **Step 6: Verificar el ciclo completo**

Con el informe abierto para corregir (Tarea 11), arregla el campo que el revisor
marcó, genera el informe y publica.

Expected:
1. El archivo descargable se llama `..._PCC_Rev.B.xlsx`.
2. En el portal, como revisor, la inspección aparece **En revisión** otra vez —
   y **no** hay una segunda fila duplicada del mismo tramo.
3. Comprobación en base:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -c "
import tomllib, db
with open('.streamlit/secrets.toml','rb') as f: s = tomllib.load(f)
db._secrets = lambda: s['supabase']
cli = db._client(write=True)
r = cli.table('inspecciones').select('id,tramo,estado,revision,nota_revision').order('creado_en', desc=True).limit(3).execute().data
for x in r: print(x)
"
```

Expected: la inspección corregida en `estado: en_revision`, `revision: B`,
`nota_revision: None`, y las observaciones ya en `resuelta`.

- [ ] **Step 7: Commit**

```bash
cp "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente/streamlit_app.py" /private/tmp/tgi_push/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(app): republicar la correccion como revision siguiente"
```

---

### Task 13: `falta_info` — el mensaje para el técnico

**Files:**
- Modify: `revision.py`
- Create: `tests/test_revision_tecnico.py`
- Modify: `streamlit_app.py` (dentro del expander del buzón)
- Modify: `db.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""Lo que falta no se arregla en el generador: se le pide al técnico."""
import revision


INSP = {"tramo": "Ansermanuevo", "tipo": "DCVG", "fecha": "2026-03-04",
        "inspector": "Juan Perez", "ot": "OT-9"}


def test_mensaje_nombra_tramo_tipo_y_lo_que_falta():
    obs = [{"categoria": "falta_info", "nota": "faltan las fotos de los defectos"},
           {"categoria": "falta_info", "nota": "falta la resistividad del K12"},
           {"categoria": "texto_campo", "nota": "esto no va en el mensaje"}]
    msg = revision.mensaje_tecnico(INSP, obs)
    assert "Ansermanuevo" in msg and "DCVG" in msg
    assert "faltan las fotos de los defectos" in msg
    assert "falta la resistividad del K12" in msg
    assert "esto no va en el mensaje" not in msg


def test_sin_falta_info_no_hay_mensaje():
    assert revision.mensaje_tecnico(INSP, [{"categoria": "texto_campo",
                                            "nota": "x"}]) == ""
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_revision_tecnico.py -q
```

Expected: FAIL con `AttributeError: module 'revision' has no attribute 'mensaje_tecnico'`.

- [ ] **Step 3: Añadir `mensaje_tecnico` a `revision.py`**

```python
def mensaje_tecnico(insp, observaciones):
    """Texto listo para copiar y mandarle al técnico lo que falta.

    No hay canal automático hacia él (la web de carga es de una sola vía), así
    que esto es deliberadamente un texto plano y no una notificación falsa.
    """
    faltantes = [o for o in (observaciones or []) if es_para_tecnico(o)]
    if not faltantes:
        return ""
    cab = (f"Hola {insp.get('inspector') or ''}, sobre la inspección "
           f"{insp.get('tipo') or ''} de {insp.get('tramo') or ''} "
           f"({insp.get('fecha') or ''}, OT {insp.get('ot') or '—'}) "
           f"falta subir:").replace("  ", " ")
    puntos = "\n".join(f"- {o.get('nota') or ''}".rstrip() for o in faltantes)
    return f"{cab}\n{puntos}\n\nSúbelo en el formulario de carga de campo. Gracias."
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_revision_tecnico.py -q
```

Expected: 2 passed.

- [ ] **Step 5: Añadir `marcar_carga_incompleta` a `db.py`**

Junto a `marcar_carga_procesada` (db.py:609):

```python
def marcar_carga_incompleta(carga_id, nota=""):
    """La carga volvió al técnico: le falta algo. Vuelve a 'pendiente' para que
    siga visible en la bandeja, con la nota de qué falta."""
    _client(write=True).table("cargas").update(
        {"estado": "pendiente", "nota": nota or None}
    ).eq("id", carga_id).execute()
```

- [ ] **Step 6: Mostrar el mensaje en el buzón**

En `streamlit_app.py`, reemplaza el bloque `if _para_tecnico:` del buzón
(Tarea 11, Step 5) por:

```python
                if _para_tecnico:
                    _msg = _rev.mensaje_tecnico(_r, _obs)
                    st.warning("Falta información que solo el técnico puede subir. "
                               "Esto no se arregla aquí.",
                               icon=":material/person:")
                    st.code(_msg, language=None)
                    st.caption("Cópialo y mándaselo. No hay canal automático hacia "
                               "el técnico todavía.")
                    if _r.get("carga_id") and st.button(
                            "Marcar la carga como incompleta",
                            key=f"inc_{_r['id']}"):
                        db.marcar_carga_incompleta(_r["carga_id"], _msg)
                        _rechazos_datos.clear()
                        _bandeja_datos.clear()
                        st.success("Carga marcada; vuelve a aparecer como pendiente.")
                        st.rerun()
```

- [ ] **Step 7: Verificar en la app**

Rechaza en el portal una inspección con una observación `falta_info` ("faltan
las fotos de los defectos"). En el generador, abre su tarjeta del buzón.

Expected: aviso amarillo + un bloque de código con el mensaje listo para copiar
que nombra el tramo, el tipo y lo que falta. **No** aparece el botón "Abrir para
corregir" si esa era la única observación.

- [ ] **Step 8: Correr la suite completa**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/ -q --ignore=tests/test_ui_cips_selector.py --ignore=tests/test_cips_duplicados.py
```

Expected: todos passed. Si algo falla, arréglalo antes de seguir: aquí termina
la Fase 1 y es la que se puede desplegar sola.

- [ ] **Step 9: Commit**

```bash
P="/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"; cp "$P/revision.py" "$P/db.py" "$P/streamlit_app.py" /private/tmp/tgi_push/ && cp "$P/tests/test_revision_tecnico.py" /private/tmp/tgi_push/tests/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(revision): mensaje al tecnico cuando falta informacion"
```

---

# FASE 2 — El asistente de Claude

La Fase 1 ya funciona sin esto. Antes de empezar, **lee las notas de rechazo
reales** que se hayan acumulado (`select nota, categoria from
observaciones_revision`): son el material con el que se afina el prompt.

---

### Task 14: `ia_revision.py` — el validador de lista blanca

Esta tarea es la barrera de seguridad y va **primero**, antes de cualquier
llamada a la API. Ningún cambio propuesto por la IA llega a la pantalla sin
pasar por aquí.

**Files:**
- Create: `ia_revision.py`
- Create: `tests/test_ia_revision_validador.py`

- [ ] **Step 1: Escribir el test que falla**

```python
"""La IA solo puede tocar metadatos y texto libre. Nunca datos de medición:
el informe se entrega a TGI bajo contrato y tiene que ser defendible."""
import ia_revision


def test_info_es_editable():
    assert ia_revision.ruta_editable("info.tramo") is True
    assert ia_revision.ruta_editable("info.ot") is True


def test_texto_de_una_fila_es_editable():
    assert ia_revision.ruta_editable("cips[12].observaciones") is True
    assert ia_revision.ruta_editable("hallazgos[0].descripcion") is True
    assert ia_revision.ruta_editable("dcvg_defectos[3].comentarios") is True


def test_datos_de_medicion_no_son_editables():
    for ruta in ("cips[12].off_mv", "cips[12].on_limpio", "cips[12].abscisa_val",
                 "dcvg_defectos[3].severidad_pct", "dcvg_defectos[3].ol_re",
                 "dcvg_defectos[3].p_re", "dcvg_defectos[3].clasificacion",
                 "cips[1].lat", "cips[1].lon", "potenciales[0].vac"):
        assert ia_revision.ruta_editable(ruta) is False, ruta


def test_rutas_raras_se_rechazan():
    for ruta in ("", None, "info", "cips.observaciones", "cips[].observaciones",
                 "__import__.os", "info.tramo; drop table"):
        assert ia_revision.ruta_editable(ruta) is False


def test_filtrar_separa_permitidos_de_descartados():
    cambios = [
        {"ruta": "info.tramo", "valor_antes": "Cartago",
         "valor_despues": "Ansermanuevo", "razon": "el revisor lo indicó"},
        {"ruta": "cips[5].off_mv", "valor_antes": -900, "valor_despues": -880,
         "razon": "se ve raro"},
    ]
    ok, fuera = ia_revision.filtrar_cambios(cambios)
    assert [c["ruta"] for c in ok] == ["info.tramo"]
    assert [c["ruta"] for c in fuera] == ["cips[5].off_mv"]


def test_aplicar_cambios_escribe_solo_lo_permitido():
    data = {"info": {"tramo": "Cartago"},
            "cips": [{"observaciones": "cruze", "off_mv": -900.0}]}
    n = ia_revision.aplicar_cambios(data, [
        {"ruta": "info.tramo", "valor_despues": "Ansermanuevo"},
        {"ruta": "cips[0].observaciones", "valor_despues": "cruce"},
        {"ruta": "cips[0].off_mv", "valor_despues": -1.0},
    ])
    assert n == 2
    assert data["info"]["tramo"] == "Ansermanuevo"
    assert data["cips"][0]["observaciones"] == "cruce"
    assert data["cips"][0]["off_mv"] == -900.0     # intacto


def test_aplicar_ignora_indices_fuera_de_rango():
    data = {"info": {}, "cips": [{"observaciones": "x"}]}
    assert ia_revision.aplicar_cambios(
        data, [{"ruta": "cips[99].observaciones", "valor_despues": "y"}]) == 0
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_ia_revision_validador.py -q
```

Expected: FAIL con `ModuleNotFoundError: No module named 'ia_revision'`.

- [ ] **Step 3: Escribir `ia_revision.py` (solo el validador)**

```python
"""Asistente de Claude para la devolución de informes rechazados.

Dos trabajos, los dos acotados:
  1. `estructurar_nota` — la nota en lenguaje natural del revisor → observaciones
     con categoría y ubicación, que es lo que enruta el buzón.
  2. `proponer_correcciones` — un diff propuesto sobre los datos ya cargados.

La IA PROPONE; el ingeniero firma. Y solo puede proponer sobre metadatos y texto
libre: `ruta_editable` es una LISTA BLANCA, no una lista negra, así que un campo
nuevo nace prohibido. Los datos de medición (potenciales, severidades, abscisas,
coordenadas) quedan fuera por construcción — el informe se entrega a TGI bajo
contrato y si la IA los "arregla" deja de ser defendible.

Sin Streamlit y sin estado: el cliente se inyecta, para poder probar sin red.
"""
from __future__ import annotations

import json
import re

MODELO = "claude-opus-5"
MAX_TOKENS = 8000

#: Único campo de una fila que la IA puede reescribir: texto que escribió una
#: persona en campo. Añadir aquí es una decisión consciente.
CAMPOS_TEXTO = ("observaciones", "descripcion", "comentarios", "ref_geografica",
                "sector", "tipo")

_RE_RUTA = re.compile(
    r"^(?:info\.(?P<campo_info>[a-z_]+)"
    r"|(?P<lista>[a-z_]+)\[(?P<idx>\d+)\]\.(?P<campo>[a-z_]+))$")


class IARevisionError(RuntimeError):
    """La API no respondió algo usable. El flujo manual sigue disponible."""


def ruta_editable(ruta) -> bool:
    """¿La IA puede tocar esta ruta? `info.*` (metadatos) y los campos de texto
    de una fila. Todo lo demás es NO, incluida cualquier ruta malformada."""
    m = _RE_RUTA.match(str(ruta or "").strip())
    if not m:
        return False
    if m.group("campo_info"):
        return True
    return m.group("campo") in CAMPOS_TEXTO


def filtrar_cambios(cambios):
    """Parte los cambios en (permitidos, descartados). Se llama ANTES de
    mostrarlos: el ingeniero no debe ni ver una propuesta sobre un potencial."""
    ok, fuera = [], []
    for c in cambios or []:
        (ok if ruta_editable(c.get("ruta")) else fuera).append(c)
    return ok, fuera


def aplicar_cambios(data, cambios) -> int:
    """Escribe en `data` los cambios que el ingeniero aprobó. Vuelve a filtrar:
    es la última barrera antes de tocar nada. Devuelve cuántos aplicó."""
    n = 0
    for c in cambios or []:
        ruta = str(c.get("ruta") or "").strip()
        if not ruta_editable(ruta):
            continue
        m = _RE_RUTA.match(ruta)
        if m.group("campo_info"):
            data.setdefault("info", {})[m.group("campo_info")] = c.get("valor_despues")
            n += 1
            continue
        filas = data.get(m.group("lista")) or []
        i = int(m.group("idx"))
        if 0 <= i < len(filas):
            filas[i][m.group("campo")] = c.get("valor_despues")
            n += 1
    return n
```

- [ ] **Step 4: Correr el test para verificar que pasa**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_ia_revision_validador.py -q
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
P="/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"; cp "$P/ia_revision.py" /private/tmp/tgi_push/ && cp "$P/tests/test_ia_revision_validador.py" /private/tmp/tgi_push/tests/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(ia): validador de lista blanca para las propuestas de la IA"
```

---

### Task 15: `ia_revision.estructurar_nota`

**Files:**
- Modify: `ia_revision.py`
- Create: `tests/test_ia_revision_llamadas.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Instalar el SDK en el venv de pruebas**

Run:

```bash
/private/tmp/venv_tgi/bin/python -m pip install anthropic
```

Expected: `Successfully installed anthropic-...`.

- [ ] **Step 2: Escribir el test que falla**

```python
"""Las llamadas a Claude, con un cliente falso: no se toca la red en los tests."""
import json

import pytest

import ia_revision


class _Bloque:
    type = "text"

    def __init__(self, text):
        self.text = text


class _Respuesta:
    def __init__(self, payload):
        self.content = [_Bloque(json.dumps(payload, ensure_ascii=False))]
        self.stop_reason = "end_turn"


class _Mensajes:
    def __init__(self, payload):
        self._payload = payload
        self.ultima_llamada = None

    def create(self, **kwargs):
        self.ultima_llamada = kwargs
        return _Respuesta(self._payload)


class _ClienteFalso:
    def __init__(self, payload):
        self.messages = _Mensajes(payload)


def test_estructurar_nota_devuelve_observaciones_normalizadas():
    cli = _ClienteFalso({"observaciones": [
        {"categoria": "datos_generales", "campo": "info.tramo",
         "abscisa_ini": None, "abscisa_fin": None,
         "nota": "dice Cartago y es Ansermanuevo"},
        {"categoria": "texto_campo", "campo": "", "abscisa_ini": 12000,
         "abscisa_fin": 15000, "nota": "comentarios ilegibles"},
    ]})
    obs = ia_revision.estructurar_nota(
        "el tramo quedó como Cartago y del K12 al K15 los comentarios no se entienden",
        {"tramo": "Cartago", "tipo": "CIPS"}, cliente=cli)
    assert len(obs) == 2
    assert obs[0]["categoria"] == "datos_generales"
    assert obs[1]["abscisa_ini"] == 12000
    assert all(o["origen"] == "ia" for o in obs)


def test_estructurar_nota_usa_el_modelo_y_el_esquema():
    cli = _ClienteFalso({"observaciones": []})
    ia_revision.estructurar_nota("algo", {}, cliente=cli)
    kw = cli.messages.ultima_llamada
    assert kw["model"] == ia_revision.MODELO
    esquema = kw["output_config"]["format"]["schema"]
    assert esquema["properties"]["observaciones"]["items"]["properties"][
        "categoria"]["enum"] == list(ia_revision.CATEGORIAS_VALIDAS)


def test_estructurar_nota_con_categoria_inventada_falla_claro():
    cli = _ClienteFalso({"observaciones": [
        {"categoria": "inventada", "campo": "", "abscisa_ini": None,
         "abscisa_fin": None, "nota": "x"}]})
    with pytest.raises(ia_revision.IARevisionError):
        ia_revision.estructurar_nota("x", {}, cliente=cli)


def test_estructurar_nota_con_json_roto_falla_claro():
    class _Roto(_ClienteFalso):
        def __init__(self):
            super().__init__({})
            self.messages.create = lambda **kw: type(
                "R", (), {"content": [_Bloque("no soy json")],
                          "stop_reason": "end_turn"})()

    with pytest.raises(ia_revision.IARevisionError):
        ia_revision.estructurar_nota("x", {}, cliente=_Roto())
```

- [ ] **Step 3: Correr el test para verificar que falla**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_ia_revision_llamadas.py -q
```

Expected: FAIL con `AttributeError: module 'ia_revision' has no attribute 'estructurar_nota'`.

- [ ] **Step 4: Añadir la llamada a `ia_revision.py`**

Añade cerca del inicio, después de `MAX_TOKENS`:

```python
import revision as _revision

CATEGORIAS_VALIDAS = _revision.CATEGORIAS
```

Y al final del módulo:

```python
# ── Cliente ─────────────────────────────────────────────────────────────────
def disponible(api_key=None) -> bool:
    """¿Se puede llamar a Claude? Sin esto la app funciona igual, a mano."""
    if not api_key:
        return False
    try:
        import anthropic          # noqa: F401
    except Exception:
        return False
    return True


def _cliente(api_key):
    try:
        import anthropic
    except Exception as e:        # el paquete es opcional, como google-generativeai
        raise IARevisionError(
            "El paquete 'anthropic' no está instalado; el asistente queda "
            "desactivado y el flujo manual sigue igual.") from e
    return anthropic.Anthropic(api_key=api_key)


def _json_de(resp):
    """Texto → dict. `output_config.format` garantiza JSON válido, pero una
    negativa o un corte por max_tokens no lo garantizan: por eso se valida."""
    if getattr(resp, "stop_reason", None) == "refusal":
        raise IARevisionError("Claude declinó la solicitud.")
    try:
        texto = next(b.text for b in resp.content if b.type == "text")
        return json.loads(texto)
    except (StopIteration, ValueError, AttributeError) as e:
        raise IARevisionError(f"Respuesta no interpretable: {e}") from e


def _pedir(cliente, api_key, sistema, payload, esquema):
    cli = cliente or _cliente(api_key)
    try:
        resp = cli.messages.create(
            model=MODELO, max_tokens=MAX_TOKENS,
            system=sistema,
            messages=[{"role": "user",
                       "content": json.dumps(payload, ensure_ascii=False,
                                             default=str)}],
            output_config={"format": {"type": "json_schema", "schema": esquema}},
        )
    except IARevisionError:
        raise
    except Exception as e:        # red, credencial, cuota: nunca tumba la app
        raise IARevisionError(f"No se pudo consultar a Claude: {e}") from e
    return _json_de(resp)


# ── 1. La nota del revisor → observaciones estructuradas ────────────────────
_SISTEMA_OBS = """\
Eres el asistente de un ingeniero de protección catódica de PCC Integrity que
revisa informes de inspección del gasoducto TGI (PAP, CIPS y DCVG).

Recibes la nota con la que un revisor rechazó un informe, escrita informalmente.
Devuélvela partida en observaciones concretas. Una observación por problema.

Categorías (elige exactamente una por observación):
- datos_generales: tramo, OT, contrato, inspector, fecha, ciclo, contratista.
- procesamiento: abscisa corrida, tramo o shapefile equivocado, picos de
  potencial, clasificación o severidad mal calculada. Obliga a reprocesar.
- texto_campo: comentarios del técnico, redacción de hallazgos, conclusiones.
- falta_info: falta un archivo, fotos o mediciones que el técnico no subió.

Reglas:
- Las abscisas van en METROS enteros. "K12" o "12+000" es 12000. Si la nota no
  da abscisa, deja null; no la inventes.
- `campo` solo cuando la nota señale uno concreto ("info.tramo",
  "hallazgo.descripcion"); si no, cadena vacía.
- `nota` reformula el problema en una frase clara y accionable, en español.
- No inventes problemas que la nota no menciona.\
"""

_ESQUEMA_OBS = {
    "type": "object",
    "properties": {
        "observaciones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "categoria": {"type": "string",
                                  "enum": list(CATEGORIAS_VALIDAS)},
                    "campo": {"type": "string"},
                    "abscisa_ini": {"type": ["integer", "null"]},
                    "abscisa_fin": {"type": ["integer", "null"]},
                    "nota": {"type": "string"},
                },
                "required": ["categoria", "campo", "abscisa_ini",
                             "abscisa_fin", "nota"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["observaciones"],
    "additionalProperties": False,
}


def estructurar_nota(nota, contexto, api_key=None, cliente=None):
    """Nota en lenguaje natural → lista de observaciones ya normalizadas.
    `cliente` es para los tests; en producción se pasa `api_key`."""
    datos = _pedir(cliente, api_key, _SISTEMA_OBS,
                   {"nota_del_revisor": nota, "informe": contexto}, _ESQUEMA_OBS)
    try:
        return [_revision.normalizar(dict(o, origen="ia"))
                for o in datos.get("observaciones") or []]
    except ValueError as e:
        raise IARevisionError(f"Claude devolvió una categoría inválida: {e}") from e
```

- [ ] **Step 5: Correr los tests para verificar que pasan**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_ia_revision_llamadas.py -q
```

Expected: 4 passed.

- [ ] **Step 6: Añadir `anthropic` a `requirements.txt`**

Al final del archivo:

```
# Asistente de revisión (ia_revision.py). Opcional: el módulo maneja su
# ausencia y el flujo de corrección funciona a mano sin él.
anthropic>=0.40,<2
```

- [ ] **Step 7: Probar contra la API de verdad (una sola llamada)**

Pon la credencial en `.streamlit/secrets.toml`:

```toml
[anthropic]
api_key = "sk-ant-..."
```

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -c "
import tomllib, ia_revision
with open('.streamlit/secrets.toml','rb') as f: s = tomllib.load(f)
obs = ia_revision.estructurar_nota(
    'el tramo quedo como Cartago pero es Ansermanuevo, y del K12 al K15 los comentarios del tecnico no se entienden. ademas faltan las fotos de los defectos',
    {'tramo':'Cartago','tipo':'DCVG','fecha':'2026-03-04'},
    api_key=s['anthropic']['api_key'])
for o in obs: print(o)
"
```

Expected: tres observaciones — una `datos_generales` sobre el tramo, una
`texto_campo` con `abscisa_ini: 12000` y `abscisa_fin: 15000`, y una
`falta_info` sobre las fotos.

- [ ] **Step 8: Commit**

```bash
P="/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"; cp "$P/ia_revision.py" "$P/requirements.txt" /private/tmp/tgi_push/ && cp "$P/tests/test_ia_revision_llamadas.py" /private/tmp/tgi_push/tests/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(ia): estructurar la nota del revisor en observaciones"
```

---

### Task 16: `ia_revision.proponer_correcciones`

**Files:**
- Modify: `ia_revision.py`
- Modify: `tests/test_ia_revision_llamadas.py`

- [ ] **Step 1: Escribir el test que falla**

Añade al final de `tests/test_ia_revision_llamadas.py`:

```python
DATA = {
    "info": {"tramo": "Cartago", "ot": "OT-9"},
    "cips": [{"abscisa_val": 12000, "observaciones": "cruze de bia", "off_mv": -900.0},
             {"abscisa_val": 13000, "observaciones": "balbula", "off_mv": -880.0},
             {"abscisa_val": 90000, "observaciones": "lejos", "off_mv": -870.0}],
}
OBS = [{"categoria": "texto_campo", "abscisa_ini": 12000, "abscisa_fin": 13000,
        "nota": "comentarios ilegibles"}]


def test_solo_manda_las_filas_de_las_abscisas_señaladas():
    cli = _ClienteFalso({"cambios": []})
    ia_revision.proponer_correcciones(OBS, DATA, "CIPS", cliente=cli)
    enviado = json.loads(cli.messages.ultima_llamada["messages"][0]["content"])
    absc = [f["abscisa_val"] for f in enviado["filas"]["cips"]]
    assert absc == [12000, 13000]      # la de 90000 no viaja


def test_descarta_las_propuestas_sobre_datos_de_medicion():
    cli = _ClienteFalso({"cambios": [
        {"ruta": "cips[0].observaciones", "valor_antes": "cruze de bia",
         "valor_despues": "cruce de vía", "razon": "ortografía"},
        {"ruta": "cips[0].off_mv", "valor_antes": -900.0, "valor_despues": -850.0,
         "razon": "parece fuera de rango"},
    ]})
    ok, fuera = ia_revision.proponer_correcciones(OBS, DATA, "CIPS", cliente=cli)
    assert [c["ruta"] for c in ok] == ["cips[0].observaciones"]
    assert [c["ruta"] for c in fuera] == ["cips[0].off_mv"]


def test_sin_abscisas_manda_una_muestra_acotada():
    cli = _ClienteFalso({"cambios": []})
    ia_revision.proponer_correcciones(
        [{"categoria": "datos_generales", "nota": "el tramo está mal"}],
        DATA, "CIPS", cliente=cli)
    enviado = json.loads(cli.messages.ultima_llamada["messages"][0]["content"])
    assert enviado["info"]["tramo"] == "Cartago"
    assert len(enviado["filas"].get("cips", [])) <= ia_revision.MAX_FILAS
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_ia_revision_llamadas.py -q
```

Expected: FAIL con `AttributeError: module 'ia_revision' has no attribute 'proponer_correcciones'`.

- [ ] **Step 3: Añadir la función a `ia_revision.py`**

Al final del módulo:

```python
# ── 2. Observaciones + datos → diff propuesto ───────────────────────────────
#: Techo de filas que viajan a la API. Un CIPS tiene ~100.000 puntos: mandarlos
#: todos sería carísimo e inútil. Las observaciones dicen dónde mirar.
MAX_FILAS = 60

#: Qué lista de `data` mira cada tipo de informe.
_LISTAS = {
    "CIPS": ("cips", "hallazgos"),
    "PAP": ("potenciales", "hallazgos"),
    "DCVG": ("dcvg_postes", "dcvg_defectos", "dcvg_resist", "dcvg_hallazgos"),
}

_ABSCISA = ("abscisa_val", "abscisa", "pk_m")


def _abscisa_de(fila):
    for k in _ABSCISA:
        if fila.get(k) is not None:
            try:
                return float(fila[k])
            except (TypeError, ValueError):
                return None
    return None


def _rangos(observaciones):
    """(ini, fin) de cada observación que señale abscisas."""
    out = []
    for o in observaciones or []:
        ini, fin = o.get("abscisa_ini"), o.get("abscisa_fin")
        if ini is not None:
            out.append((float(ini), float(fin if fin is not None else ini)))
    return out


def _filas_relevantes(data, tipo, observaciones):
    """Solo las filas que las observaciones señalan; si no señalan ninguna, una
    muestra acotada para que el modelo vea la forma del dato."""
    rangos = _rangos(observaciones)
    seleccion = {}
    for lista in _LISTAS.get(tipo, ()):
        filas = data.get(lista) or []
        if rangos:
            elegidas = [f for f in filas
                        if any(a is not None and ini <= a <= fin
                               for ini, fin in rangos
                               for a in (_abscisa_de(f),))]
        else:
            elegidas = list(filas)
        if elegidas:
            seleccion[lista] = elegidas[:MAX_FILAS]
    return seleccion


_SISTEMA_DIFF = """\
Eres el asistente de un ingeniero de PCC Integrity que va a corregir un informe
de inspección rechazado.

Recibes las observaciones del revisor, los Datos Generales y SOLO las filas
señaladas. Propón los cambios mínimos que resuelvan cada observación.

Puedes proponer cambios ÚNICAMENTE sobre:
- `info.<campo>` — Datos Generales (tramo, ot, contrato, contratista, ...).
- `<lista>[<i>].<campo>` donde campo sea texto escrito por una persona:
  observaciones, descripcion, comentarios, ref_geografica, sector, tipo.

NUNCA propongas cambios sobre potenciales (on/off), severidades, abscisas,
coordenadas, clasificaciones ni ningún valor medido o calculado: son el dato de
ingeniería que se entrega bajo contrato. Si una observación pide algo así,
devuelve el cambio con razon explicando que requiere reprocesar los crudos y
ruta "info.nota_reproceso".

Al corregir texto de campo: arregla ortografía y claridad en español técnico
colombiano de protección catódica (cruce, aéreo, tensión, válvula, línea, río,
abscisado, rocería). NO cambies el significado ni añadas información que el
técnico no escribió.

`valor_antes` debe ser exactamente el valor actual. `razon` es una frase corta.\
"""

_ESQUEMA_DIFF = {
    "type": "object",
    "properties": {
        "cambios": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ruta": {"type": "string"},
                    "valor_antes": {"type": ["string", "number", "null"]},
                    "valor_despues": {"type": ["string", "number", "null"]},
                    "razon": {"type": "string"},
                },
                "required": ["ruta", "valor_antes", "valor_despues", "razon"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["cambios"],
    "additionalProperties": False,
}


def proponer_correcciones(observaciones, data, tipo, api_key=None, cliente=None):
    """Devuelve (permitidos, descartados). Los índices de `ruta` son relativos a
    las filas ENVIADAS, así que se remapean a los índices reales de `data` antes
    de devolverlos: si no, un cambio aterrizaría en la fila equivocada."""
    seleccion = _filas_relevantes(data, tipo, observaciones)
    indices = {lista: [(data.get(lista) or []).index(f) for f in filas]
               for lista, filas in seleccion.items()}
    payload = {
        "observaciones": [
            {k: o.get(k) for k in ("categoria", "campo", "abscisa_ini",
                                   "abscisa_fin", "nota")}
            for o in observaciones or []],
        "info": dict(data.get("info") or {}),
        "filas": seleccion,
    }
    datos = _pedir(cliente, api_key, _SISTEMA_DIFF, payload, _ESQUEMA_DIFF)

    remapeados = []
    for c in datos.get("cambios") or []:
        m = _RE_RUTA.match(str(c.get("ruta") or "").strip())
        if m and m.group("lista"):
            lista, i = m.group("lista"), int(m.group("idx"))
            reales = indices.get(lista) or []
            if not (0 <= i < len(reales)):
                continue                      # índice inventado: se descarta
            c = dict(c, ruta=f"{lista}[{reales[i]}].{m.group('campo')}")
        remapeados.append(c)
    return filtrar_cambios(remapeados)
```

- [ ] **Step 4: Correr los tests para verificar que pasan**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/test_ia_revision_llamadas.py tests/test_ia_revision_validador.py -q
```

Expected: 14 passed.

- [ ] **Step 5: Probar contra la API de verdad**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -c "
import tomllib, ia_revision
with open('.streamlit/secrets.toml','rb') as f: s = tomllib.load(f)
data = {'info': {'tramo':'Cartago','ot':'OT-9'},
        'cips': [{'abscisa_val':12000,'observaciones':'cruze de bia destapado','off_mv':-900.0},
                 {'abscisa_val':12500,'observaciones':'balbula serrada','off_mv':-880.0}]}
obs = [{'categoria':'texto_campo','abscisa_ini':12000,'abscisa_fin':12500,
        'nota':'los comentarios del tecnico estan mal escritos'},
       {'categoria':'datos_generales','campo':'info.tramo',
        'nota':'el tramo es Ansermanuevo, no Cartago'}]
ok, fuera = ia_revision.proponer_correcciones(obs, data, 'CIPS', api_key=s['anthropic']['api_key'])
print('PROPUESTOS:');  [print(' ', c) for c in ok]
print('DESCARTADOS:'); [print(' ', c) for c in fuera]
"
```

Expected: propuestas para `info.tramo` → Ansermanuevo, `cips[0].observaciones`
→ "cruce de vía destapado" y `cips[1].observaciones` → "válvula cerrada". La
lista de descartados debe estar vacía (el prompt ya la desvía) — si aparece algo
sobre `off_mv`, el validador hizo su trabajo y hay que ajustar el prompt.

- [ ] **Step 6: Commit**

```bash
P="/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"; cp "$P/ia_revision.py" /private/tmp/tgi_push/ && cp "$P/tests/test_ia_revision_llamadas.py" /private/tmp/tgi_push/tests/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(ia): proponer correcciones acotadas a las abscisas senaladas"
```

---

### Task 17: Botón "Analizar" en el portal

**Files:**
- Modify: `portal_app.py` (el popover de rechazo de la Tarea 9)

- [ ] **Step 1: Añadir el analizador antes del `st.data_editor`**

Dentro del `with cb.popover("✋ Rechazar"):`, entre el `st.caption(...)` y el
`_obs = st.data_editor(...)`:

```python
            _apikey = ""
            try:
                _apikey = str(st.secrets.get("anthropic", {}).get("api_key", ""))
            except Exception:
                _apikey = ""
            _sem = f"iaobs_{insp['id']}"
            if _apikey:
                _nota_libre = st.text_area(
                    "Escríbelo como lo dirías", key=f"libre_{insp['id']}",
                    placeholder="el tramo quedó como Cartago pero es Ansermanuevo, "
                                "y del K12 al K15 los comentarios no se entienden",
                    height=80)
                if st.button("✨ Analizar", key=f"ia_{insp['id']}"):
                    import ia_revision
                    with st.spinner("Clasificando lo que reportaste..."):
                        try:
                            st.session_state[_sem] = [
                                {k: o.get(k) for k in ("categoria", "campo",
                                                       "abscisa_ini", "abscisa_fin",
                                                       "nota")}
                                for o in ia_revision.estructurar_nota(
                                    _nota_libre,
                                    {"tramo": insp.get("tramo"),
                                     "tipo": insp.get("tipo"),
                                     "fecha": str(insp.get("fecha") or "")},
                                    api_key=_apikey)]
                        except ia_revision.IARevisionError as _e:
                            st.warning(f"{_e} Llena la tabla a mano.")
                    st.rerun()
                st.caption("Revisa y corrige lo que proponga: se guarda lo que "
                           "quede en la tabla, no lo que dijo la IA.")
```

- [ ] **Step 2: Sembrar la tabla con lo que devolvió la IA**

Cambia el primer argumento del `st.data_editor` de la lista fija a:

```python
                st.session_state.get(_sem) or [
                    {"categoria": "datos_generales", "campo": "",
                     "abscisa_ini": None, "abscisa_fin": None, "nota": ""}],
```

- [ ] **Step 3: Limpiar el semillero al confirmar**

Dentro del `else:` que hace el `st.rerun()` tras rechazar correctamente, antes
del `_refrescar()`:

```python
                        st.session_state.pop(_sem, None)
```

- [ ] **Step 4: Verificar en el portal**

Abre el portal como revisor, entra a una inspección en revisión, abre
"✋ Rechazar", escribe la frase de ejemplo del placeholder y oprime "✨ Analizar".

Expected: la tabla se rellena con 2-3 filas ya clasificadas, con las abscisas en
metros. Cambia una categoría a mano y confirma: se guarda **lo que quedó en la
tabla**.

- [ ] **Step 5: Verificar que sin credencial no se rompe**

Comenta la sección `[anthropic]` de `.streamlit/secrets.toml` y recarga.

Expected: el popover funciona igual, sin el área de texto ni el botón
"✨ Analizar". Se puede rechazar llenando la tabla a mano. Vuelve a poner la
credencial cuando termines.

- [ ] **Step 6: Commit**

```bash
cp "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente/portal_app.py" /private/tmp/tgi_push/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(portal): analizar la nota de rechazo con Claude"
```

---

### Task 18: Diff aprobable en el generador

**Files:**
- Modify: `streamlit_app.py` (dentro del expander del buzón, tras los botones)

- [ ] **Step 1: Añadir el bloque de sugerencias**

En el expander de cada rechazo del buzón, después del bloque
`if _para_tecnico:`, añade:

```python
                _apikey = ""
                try:
                    _apikey = str(st.secrets.get("anthropic", {}).get("api_key", ""))
                except Exception:
                    _apikey = ""
                _abierto = (st.session_state.get("corrigiendo") or {}).get("id")
                if _apikey and _corregibles and _abierto == _r["id"]:
                    import ia_revision
                    _kd = f"diff_{_r['id']}"
                    if st.button("✨ Sugerir arreglos", key=f"sug_{_r['id']}"):
                        with st.spinner("Revisando las observaciones..."):
                            try:
                                _ok, _fuera = ia_revision.proponer_correcciones(
                                    _corregibles, data, _r.get("tipo"),
                                    api_key=_apikey)
                                st.session_state[_kd] = {
                                    "ok": [dict(c, aplicar=True) for c in _ok],
                                    "fuera": _fuera}
                            except ia_revision.IARevisionError as _e:
                                st.warning(f"{_e} Corrige a mano.")
                        st.rerun()

                    _diff = st.session_state.get(_kd)
                    if _diff:
                        st.markdown("**Cambios propuestos** — marca los que "
                                    "quieras aplicar:")
                        _edit = st.data_editor(
                            _diff["ok"], key=f"ed_{_r['id']}",
                            use_container_width=True, hide_index=True,
                            disabled=["ruta", "valor_antes", "valor_despues", "razon"],
                            column_config={
                                "aplicar": st.column_config.CheckboxColumn("✓"),
                                "ruta": st.column_config.TextColumn("Dónde"),
                                "valor_antes": st.column_config.TextColumn("Antes"),
                                "valor_despues": st.column_config.TextColumn("Después"),
                                "razon": st.column_config.TextColumn("Por qué",
                                                                    width="large"),
                            })
                        if _diff["fuera"]:
                            st.caption(
                                f"🛡️ {len(_diff['fuera'])} propuesta(s) descartadas "
                                f"por tocar datos de medición: "
                                + ", ".join(c.get("ruta", "?")
                                            for c in _diff["fuera"]))
                        if st.button("Aplicar los marcados", key=f"apl_{_r['id']}",
                                     type="primary"):
                            _n = ia_revision.aplicar_cambios(
                                data, [c for c in _edit if c.get("aplicar")])
                            _info_camb = {
                                c["ruta"].split(".", 1)[1]: c["valor_despues"]
                                for c in _edit
                                if c.get("aplicar") and c["ruta"].startswith("info.")}
                            if _info_camb:
                                st.session_state.pending_autofill = dict(
                                    st.session_state.get("pending_autofill") or {},
                                    **_info_camb)
                            st.session_state.pop(_kd, None)
                            st.session_state.flash_autocarga = (
                                f"{_n} cambio(s) aplicados. Revisa Datos Generales, "
                                f"vuelve a generar y publica como Rev."
                                f"{nombres.siguiente_revision(_r.get('revision'))}.")
                            st.rerun()
                elif _apikey and _corregibles:
                    st.caption("Abre el informe para corregir y aparecerá "
                               "'✨ Sugerir arreglos'.")
```

- [ ] **Step 2: Verificar el ciclo completo con IA**

1. En el portal (revisor), rechaza un informe con "✨ Analizar" describiendo un
   error de tramo y comentarios mal escritos.
2. En el generador, buzón → "🔧 Abrir para corregir".
3. Vuelve al buzón y oprime "✨ Sugerir arreglos".

Expected: una tabla de cambios con "Dónde / Antes / Después / Por qué" y todos
marcados. Desmarca uno, oprime "Aplicar los marcados".

Expected: el mensaje dice cuántos se aplicaron; en Datos Generales el tramo ya
está corregido; el cambio desmarcado NO se aplicó.

4. Genera el informe y publica.

Expected: archivo `..._Rev.B.xlsx`, la inspección vuelve a "En revisión" en el
portal sin duplicarse, y sus observaciones quedan en `resuelta`.

- [ ] **Step 3: Correr la suite completa**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/ -q --ignore=tests/test_ui_cips_selector.py --ignore=tests/test_cips_duplicados.py
```

Expected: todos passed.

- [ ] **Step 4: Commit**

```bash
cp "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente/streamlit_app.py" /private/tmp/tgi_push/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "feat(app): diff aprobable de las sugerencias de Claude"
```

---

### Task 19: Documentar y desplegar

**Files:**
- Modify: `TGI_V1_Codigo_Fuente/AGENTS.md`

- [ ] **Step 1: Documentar el flujo en AGENTS.md**

Añade una sección `### 10.14` al final del capítulo 10:

```markdown
### 10.14 Devolución de informes rechazados (+ asistente Claude) — 2026-09
Un rechazo en el portal dejó de ser un párrafo muerto: ahora enruta la corrección.
- **`portal/schema_v9.sql`**: `inspecciones.carga_id` (de qué carga salió),
  `.contexto` jsonb (el `info` completo + selección de tramo, que la fila no guarda)
  y `.revision` ('A','B'...); tabla `observaciones_revision` (categoría, campo,
  abscisas, nota, origen revisor|ia, estado). RLS: solo service_role.
- **4 categorías** (`revision.CATEGORIAS`): `datos_generales` · `procesamiento`
  (la ÚNICA que obliga a reprocesar crudos) · `texto_campo` · `falta_info` (NO
  vuelve al generador: `revision.mensaje_tecnico` arma el texto para el técnico,
  no hay canal automático hacia él).
- **`revision.py`**: mapeadores inversos BD→generador y `rehidratar(detalle, tipo)`.
  La rehidratación sale de las filas YA publicadas, así que funciona aunque el
  informe se haya cargado a mano (sin `carga_id`). **Los derivados (`estado`,
  `p_re`, `severidad_pct`, `clasificacion`) NO se rehidratan**: los recalculan
  `dashboard.estado_cp` y `db._severidad_dcvg` — por eso el `%` vs. fracción del
  DCVG no puede corromperse. Cubierto por `tests/test_revision_roundtrip.py`:
  **si ese test se rompe, el informe corregido sale con datos corridos y no
  lanza ningún error.**
- **`db.py`**: `_*_filas` puros (para poder probar el round-trip sin Supabase),
  `_crear_o_reemplazar` (republicar ACTUALIZA la fila y reescribe las hijas, no
  inserta un duplicado), `rechazar_inspeccion(..., observaciones=[...])`,
  `observaciones_de`, `listar_rechazadas`, `marcar_observaciones`,
  `marcar_carga_incompleta`.
- **`nombres.py`**: `nombre_archivo(..., revision='A')` + `siguiente_revision`.
- **Flujo**: portal (revisor) rechaza con categorías → generador, pestaña
  Archivos, "🔧 Rechazos por corregir" → "Abrir para corregir" (rehidrata) o
  "Reprocesar desde crudos" (si hay `carga_id` y la causa es procesamiento) →
  arreglar → generar → publicar (actualiza la misma inspección como Rev.B y
  vuelve a `en_revision`).
- **`ia_revision.py`** (`claude-opus-5`, `st.secrets['anthropic']['api_key']`):
  `estructurar_nota` (nota informal → observaciones) y `proponer_correcciones`
  (→ diff aprobable). **`ruta_editable` es una LISTA BLANCA**: solo `info.*` y
  campos de texto (`CAMPOS_TEXTO`); cualquier propuesta sobre potenciales,
  severidades, abscisas o coordenadas se descarta ANTES de mostrarse, y
  `aplicar_cambios` vuelve a filtrar. `anthropic` es opcional: sin credencial
  todo el flujo funciona a mano. Solo viajan a la API las filas de las abscisas
  señaladas (`MAX_FILAS = 60`), nunca los ~100.000 puntos de un CIPS.
```

- [ ] **Step 2: Marcar el pendiente resuelto**

En la sección `## 9. Pendientes conocidos`, no hay entrada de esto porque es
nuevo; no toques nada ahí.

- [ ] **Step 3: Verificación final antes de publicar**

Run:

```bash
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente" && /private/tmp/venv_tgi/bin/python -m pytest tests/ -q --ignore=tests/test_ui_cips_selector.py --ignore=tests/test_cips_duplicados.py
```

Expected: todos passed. **No sigas si algo falla.**

- [ ] **Step 4: Commit de la documentación**

```bash
cp "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente/AGENTS.md" /private/tmp/tgi_push/
```

```bash
cd /private/tmp/tgi_push && git add -A
```

```bash
cd /private/tmp/tgi_push && git commit -m "docs: flujo de devolucion de rechazos en AGENTS.md"
```

- [ ] **Step 5: Preguntar al usuario antes del push**

El push a `main` **redespliega las 3 apps de Streamlit Cloud a la vez**.
Pregúntale al usuario si es buen momento (no durante una demo con el cliente) y
espera su confirmación.

- [ ] **Step 6: Push**

```bash
cd /private/tmp/tgi_push && git push
```

Expected: `main -> main`. En ~1 minuto las tres apps quedan redesplegadas.

- [ ] **Step 7: Recordarle al usuario lo que falta de su lado**

Dos cosas que el agente no puede hacer:
1. Correr `portal/schema_v9.sql` en Supabase **si no lo corrió en la Tarea 1**.
2. Poner `[anthropic] api_key` en los Secrets de Streamlit Cloud de las apps de
   **procesamiento** y **portal** (en local basta `.streamlit/secrets.toml`).
   Sin eso, en la nube el asistente no aparece y el flujo queda manual.

---

## Notas de diseño que no se deben perder

- **El round-trip es el test crítico.** Un desajuste en `revision._CIPS` o
  `_DEFECTOS` no lanza excepción: escribe el informe con los datos en la columna
  equivocada. Si añades una columna a `puntos_cips` u otra tabla hija, añádela
  también al mapa y al `*_ORIG` del test.
- **Los derivados no se rehidratan** a propósito. No los "arregles" añadiéndolos
  al mapa: se recalculan, y ahí es donde vive la conversión `%` ↔ fracción del
  DCVG.
- **`ruta_editable` es lista blanca.** Si mañana se añade un campo a una fila,
  nace prohibido para la IA. Es lo correcto: abrirlo debe ser una decisión
  consciente, no un descuido.
- **Republicar actualiza en sitio.** Si en el futuro se quiere historial de
  revisiones, la salida no es insertar una fila nueva (el portal mostraría
  duplicados al cliente) sino una tabla `revisiones_inspeccion` aparte.
