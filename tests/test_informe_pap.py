"""Leer un informe PAP YA GENERADO para publicarlo al portal: lo que sale del
lector debe ser lo mismo que el generador escribió en la plantilla."""
import os

import pytest

from generator import ReportGenerator
from informe_pap import leer_informe_pap


def _pots(n):
    out = []
    for i in range(n):
        out.append({'abscisa': i * 1000, 'fecha': '27/09/2026',
                    'ref_geografica': 'Poste de Potencial',
                    'on_mv': -1000 - i, 'off_mv': -900 - i, 'vac': 0.2 + i / 100,
                    'resistencia': 0.3, 'ir_on_off': -100,
                    'lat': 4.0 - i / 100, 'lon': -73.75,
                    'observaciones': 'Poste de potencial'})
    # un poste sin lectura (p.ej. avispas): se conserva, sin potenciales
    out[5].update(on_mv=None, off_mv=None, vac=None, ir_on_off=None,
                  ref_geografica='', observaciones='Poste con avispas')
    return out


@pytest.fixture(scope="module", params=[10, 69])
def informe(request, tmp_path_factory):
    n = request.param
    gen = ReportGenerator()
    gen.fill_potenciales_pap(_pots(n))
    info = {'fecha': '27/09/2026', 'gasoducto': 'Gasoducto_del_Ariari',
            'tramo': 'Gasoducto del Ariari', 'tipo_inspeccion': 'PAP',
            'contrato': '551007370', 'contratista': 'PCC', 'ot': '1300012836',
            'inspector': 'Jose Luis Paez'}
    gen.fill_hallazgos([{
        'abscisa_inicio': 1000, 'abscisa_fin': 1000, 'longitud': 0,
        'gasoducto': 'Gasoducto_del_Ariari', 'tramo': 'Gasoducto del Ariari',
        'lat_inicio': 4.0, 'lon_inicio': -73.75, 'fecha': '27/09/2026',
        'tipo': 'Vaquela en mal estado', 'descripcion': 'Vaquela mala'}], info)
    out = os.path.join(tmp_path_factory.mktemp("pap"), "PAP_REP.xlsx")
    gen.save(out)
    return n, leer_informe_pap(out)


def test_lee_todos_los_postes(informe):
    n, r = informe
    p = r['potenciales']
    # ni las filas numeradas vacías de la plantilla ni el bloque de firmas
    assert [x['abscisa'] for x in p] == [i * 1000 for i in range(n)]
    assert p[0]['on_mv'] == -1000 and p[0]['off_mv'] == -900
    assert p[0]['vac'] == pytest.approx(0.2)
    assert p[0]['resistencia'] == pytest.approx(0.3)
    assert p[0]['lat'] == pytest.approx(4.0) and p[0]['lon'] == pytest.approx(-73.75)
    assert p[0]['ref_geografica'] == 'Poste de Potencial'
    assert p[0]['fecha'] == '27/09/2026'
    assert p[-1]['off_mv'] == -900 - (n - 1)


def test_poste_sin_lectura_se_conserva(informe):
    _, r = informe
    p = r['potenciales'][5]
    assert p['abscisa'] == 5000 and p['off_mv'] is None and p['on_mv'] is None
    assert 'avispas' in p['observaciones']


def test_hallazgos_e_info(informe):
    _, r = informe
    assert r['info']['tipo_inspeccion'] == 'PAP'
    assert len(r['hallazgos']) == 1
    assert r['hallazgos'][0]['tipo'] == 'Vaquela en mal estado'


def test_filas_para_el_portal(informe):
    import db
    n, r = informe
    filas = db._puntos_pap_filas('x', r['potenciales'])
    assert len(filas) == n
    assert filas[0]['abscisa'] == 0 and filas[0]['fecha'] == '2026-09-27'
    assert filas[5]['off_mv'] is None


def test_rechaza_un_informe_que_no_es_pap(tmp_path):
    import openpyxl
    p = os.path.join(tmp_path, "x.xlsx")
    openpyxl.Workbook().save(p)
    with pytest.raises(ValueError):
        leer_informe_pap(p)
