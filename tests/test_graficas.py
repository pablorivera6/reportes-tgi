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
