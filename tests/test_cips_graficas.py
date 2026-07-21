"""CIPS: la abscisa debe escribirse como NÚMERO (metros) para que el formato
personalizado \\K\\ 000\\+000 la muestre y para que la serie X (numérica) de
las gráficas VDC/Interferencia del template CIPS encuentre puntos y dibuje."""
import os
import re
import zipfile

from generator import ReportGenerator, resource_path


def _cips(n):
    """Dicts al estilo del cips_adapter (incluye un punto con abscisa 0)."""
    return [{
        'abscisa_val': i * 25,               # metros; el primero es 0
        'referencia': f'ref {i}',
        'observaciones': '',
        'on_mv': -1100 - (i % 5) * 10,
        'off_mv': -900 - (i % 7) * 8,
        'on_limpio': -1100 - (i % 5) * 10,
        'off_limpio': -900 - (i % 7) * 8,
        'lat': 4.0, 'lon': -73.0,
    } for i in range(n)]


def test_abscisa_cips_es_numerica_y_completa():
    gen = ReportGenerator(resource_path("CIPS EN BLANCO.xlsx"))
    datos = _cips(30)
    gen.fill_cips(datos)
    ws = gen.wb['Potenciales CIPS']
    for i in range(len(datos)):
        b = ws.cell(row=12 + i, column=2).value
        assert isinstance(b, (int, float)), (
            f"fila {12+i}: abscisa debe ser número, es {b!r}")
    # el primer punto (abscisa 0) NO puede quedar vacío
    assert ws.cell(row=12, column=2).value == 0
    # G/H "POTENCIAL NEGATIVO 1 TGI [CORREGIDO]" deben quedar VACÍAS:
    # el informe solo lleva los potenciales medidos (E/F)
    for i in range(3):
        assert ws.cell(row=12 + i, column=7).value in (None, '')
        assert ws.cell(row=12 + i, column=8).value in (None, '')
        assert ws.cell(row=12 + i, column=5).value is not None


def test_grafica_cips_recorta_rango_a_datos(tmp_path):
    n = 40
    gen = ReportGenerator(resource_path("CIPS EN BLANCO.xlsx"))
    datos = _cips(n)
    gen.fill_cips(datos)
    gen.fill_graficas_cips(datos, {'tramo': 'T', 'tipo_ducto': 'Linea'})
    out = os.path.join(tmp_path, "cips.xlsx")
    gen.save(out)

    z = zipfile.ZipFile(out)
    charts = [c for c in z.namelist() if re.search(r'charts/chart\d+\.xml', c)]
    assert charts
    encontrada = False
    for c in charts:
        d = z.read(c).decode("utf8", "replace")
        cips_series = [r for r in re.findall(r'<f>([^<]*)</f>', d)
                       if 'Potenciales CIPS' in r]
        for r in cips_series:
            encontrada = True
            assert f"${11 + n}" in r, f"serie no recortada a fila {11+n}: {r}"
            assert "$29347" not in r, f"serie sigue con rango gigante: {r}"
    assert encontrada, "no se hallaron series de datos CIPS en las gráficas"
