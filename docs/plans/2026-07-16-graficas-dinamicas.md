# Gráficas dinámicas Implementation Plan

**Goal:** Que las 3 gráficas del informe (VDC, Interferencia, VAC) tomen el rango de datos completo (primer→último poste) y ajusten sus ejes a los datos reales, en vez del rango/ejes fijos del template.

**Architecture:** Nuevo método `ReportGenerator.ajustar_graficas(potenciales)` en `generator.py`, llamado al final de `fill_graficas`. Reescribe las series que apuntan a "Potenciales PAP" (fila 12 → 11+N), fija eje X a la abscisa máxima, eje Y a los datos + 10% margen manteniendo visibles las líneas de criterio, y elimina las series `#REF!` del template. Validado end-to-end contra ReportGenerator real y el XML resultante.

**Tech Stack:** openpyxl (edición de charts vía objetos), Python 3.11.

**Rama:** `feat/cips-lrs` (commits separados).

---

### Task 1: Método `ajustar_graficas` + integración en `fill_graficas`

**Files:**
- Modify: `SRC/generator.py` (import `math`; nuevo método; llamada en `fill_graficas`)
- Test: `SRC/tests/test_graficas.py`

- [ ] **Step 1: Escribir el test que falla** — `SRC/tests/test_graficas.py`:

```python
import re
import os
import zipfile
from generator import ReportGenerator


def _pots(n):
    return [{'abscisa': i * 70, 'on_mv': -1150 - (i % 5) * 10,
             'off_mv': -900 - (i % 7) * 8, 'vac': 2.0 + (i % 4),
             'ir_on_off': 30 + (i % 6) * 5,
             'ref_geografica': '', 'observaciones': ''} for i in range(n)]


def _info():
    return {'fecha': '', 'gasoducto': 'G', 'tramo': 'T', 'tipo_ducto': 'Linea',
            'longitud_km': 8.3, 'diametro': '12', 'tipo_recubrimiento': 'FBE'}


def test_graficas_rango_dinamico_y_sin_ref(tmp_path):
    n = 120
    pot = _pots(n)
    gen = ReportGenerator()
    gen.fill_potenciales_pap(pot)
    gen.fill_graficas(pot, _info())
    out = os.path.join(tmp_path, "r.xlsx")
    gen.save(out)

    z = zipfile.ZipFile(out)
    charts = [c for c in z.namelist() if re.search(r'charts/chart\d+\.xml', c)]
    assert charts
    for c in charts:
        d = z.read(c).decode("utf8", "replace")
        assert "#REF!" not in d, f"{c} conserva series #REF!"
        pap = [r for r in re.findall(r'<f>([^<]*)</f>', d) if 'Potenciales PAP' in r]
        assert pap, f"{c} sin series de datos"
        for r in pap:
            assert "$12:" in r, f"{c} no empieza en fila 12: {r}"
            assert f"${11 + n}" in r, f"{c} no termina en fila {11 + n}: {r}"


def test_graficas_sin_datos_no_rompe():
    gen = ReportGenerator()
    gen.ajustar_graficas([])  # no debe lanzar
```

- [ ] **Step 2: Correr y confirmar FALLO** (`AttributeError: ... 'ajustar_graficas'`):
```
cd "/Users/pabloandresrivera/Desktop/Reportes TGI ejecutable/TGI_V1_Codigo_Fuente"
QT_QPA_PLATFORM=offscreen "<PY>" -m pytest tests/test_graficas.py -v
```

- [ ] **Step 3: Añadir `import math`** al inicio de `generator.py` (tras los otros imports).

- [ ] **Step 4: Añadir el método a la clase `ReportGenerator`** (p.ej. justo antes de `def save(self`):

```python
    @staticmethod
    def _nice_floor(v, step):
        return math.floor(v / step) * step

    @staticmethod
    def _nice_ceil(v, step):
        return math.ceil(v / step) * step

    def ajustar_graficas(self, potenciales):
        """Ajusta rango de series y ejes de las 3 graficas a los datos reales.

        - Series 'Potenciales PAP' de fila 12 (primer poste) a 11+N.
        - Eje X: 0 hasta la abscisa maxima (redondeada a 100 m).
        - Eje Y: min/max de los datos + 10% margen, manteniendo visibles las
          lineas de criterio. Elimina las series #REF! rotas del template.
        """
        import re
        if not potenciales:
            return
        n = len(potenciales)
        last = 11 + n
        max_absc = max((p.get('abscisa') or 0) for p in potenciales)
        x_max = self._nice_ceil(max_absc, 100) if max_absc > 0 else 100

        cfgs = [
            (self.ws_grafica_vdc,    ['on_mv', 'off_mv'], [-850, -1200], 100),
            (self.ws_grafica_interf, ['ir_on_off'],       [50],          10),
            (self.ws_grafica_vac,    ['vac'],             [15],          2),
        ]

        def _ref_ok(s):
            for part in (s.xVal, s.yVal):
                f = part.numRef.f if (part and part.numRef) else None
                if f is None or '#REF!' in f:
                    return False
            return True

        for ws, keys, criterios, step in cfgs:
            if ws is None or not getattr(ws, '_charts', None):
                continue
            chart = ws._charts[0]

            series_validas = [s for s in chart.series if _ref_ok(s)]
            for s in series_validas:
                fx = s.xVal.numRef.f
                if 'Potenciales PAP' in fx:
                    s.xVal.numRef.f = re.sub(r'\$B\$\d+:\$B\$\d+',
                                             f'$B$12:$B${last}', fx)
                    col = re.search(r'\$([A-Z]+)\$\d+:', s.yVal.numRef.f).group(1)
                    s.yVal.numRef.f = f"'Potenciales PAP'!${col}$12:${col}${last}"
                    if s.xVal.numRef.numCache:
                        s.xVal.numRef.numCache = None
                    if s.yVal.numRef.numCache:
                        s.yVal.numRef.numCache = None
            chart.series = series_validas

            chart.x_axis.scaling.min = 0
            chart.x_axis.scaling.max = x_max

            vals = [p.get(k) for k in keys for p in potenciales if p.get(k) is not None]
            if vals:
                lo = min(vals + criterios)
                hi = max(vals + criterios)
                span = (hi - lo) or 1
                margin = span * 0.1
                chart.y_axis.scaling.min = self._nice_floor(lo - margin, step)
                chart.y_axis.scaling.max = self._nice_ceil(hi + margin, step)
```

- [ ] **Step 5: Llamar al método al final de `fill_graficas`.** Localiza el final del método `fill_graficas` (tras el bloque `--- Gráfica VAC ---`, justo antes de `def fill_hallazgos`). Añade como última línea del cuerpo de `fill_graficas`:
```python
        self.ajustar_graficas(potenciales)
```

- [ ] **Step 6: Correr y confirmar que PASA:**
```
QT_QPA_PLATFORM=offscreen "<PY>" -m pytest tests/test_graficas.py -v
```

- [ ] **Step 7: Correr la suite completa** (nada roto):
```
QT_QPA_PLATFORM=offscreen "<PY>" -m pytest tests/ -q
```

- [ ] **Step 8: Commit:**
```
git add -A && git -c user.name='TGI Dev' -c user.email='dev@pcc.local' commit -m "feat: graficas con rango dinamico y ejes ajustados a los datos"
```
