"""Leer un informe CIPS YA GENERADO para publicarlo al portal: lo que sale del
lector debe ser lo mismo que el generador escribió en la plantilla."""
import os

import pytest

from generator import ReportGenerator, resource_path
from informe_cips import leer_informe_cips


@pytest.fixture(scope="module")
def informe(tmp_path_factory):
    gen = ReportGenerator(resource_path("CIPS EN BLANCO.xlsx"))
    cips = [
        {'abscisa_val': 147, 'fecha': '21/08/2026', 'referencia': '',
         'on_limpio': -1356.16, 'off_limpio': -754.37, 'vac': 0.4,
         'metal_on': -10.5, 'metal_off': -8.0, 'far_on': -1200, 'far_off': -900,
         'near_on': -1300, 'near_off': -950,
         'lat': 2.9676957, 'lon': -75.2545024},
        {'abscisa_val': 385, 'fecha': '21/08/2026',
         'referencia': 'PK 15.362 atenuación de corriente',
         'on_limpio': -1414.87, 'off_limpio': -801.98,
         'observaciones': 'PK 15.362 atenuación de corriente',
         'lat': 2.9697119, 'lon': -75.2544763},
        {'abscisa_val': 15601, 'fecha': '24/08/2026', 'referencia': '',
         'on_limpio': -479.43, 'off_limpio': -403.5,
         'lat': 3.0776628, 'lon': -75.2921995},
    ]
    gen.fill_cips(cips)
    info = {'fecha': '20/08/2026 al 24/08/2026', 'gasoducto': 'Centro-Oriente',
            'tramo': 'Dina - Tello', 'tipo_inspeccion': 'CIPS',
            'contrato': '551007370', 'contratista': 'PCC', 'ot': '1300012991',
            'inspector': 'Evelio Alvarez'}
    gen.fill_hallazgos([{
        'abscisa_inicio': 385, 'gasoducto': 'Centro-Oriente',
        'tramo': 'Dina - Tello', 'lat_inicio': 2.9697119,
        'lon_inicio': -75.2544763, 'fecha': '21/08/2026',
        'tipo': 'Atenuación de corriente',
        'descripcion': 'PK 15.362 atenuación de corriente'}], info)
    out = os.path.join(tmp_path_factory.mktemp("cips"), "CIPS_REP.xlsx")
    gen.save(out)
    return leer_informe_cips(out)


def test_lee_todas_las_lecturas_en_orden(informe):
    c = informe['cips']
    assert [p['abscisa_val'] for p in c] == [147, 385, 15601]
    # E/F del informe son el potencial oficial (ya suavizado)
    assert c[0]['off_limpio'] == pytest.approx(-754.37)
    assert c[0]['on_limpio'] == pytest.approx(-1356.16)
    assert c[0]['off_mv'] == pytest.approx(-754.37)
    assert c[0]['metal_on'] == pytest.approx(-10.5)
    assert c[0]['far_off'] == pytest.approx(-900)
    assert c[0]['near_off'] == pytest.approx(-950)
    assert c[0]['lat'] == pytest.approx(2.9676957)
    assert c[2]['lon'] == pytest.approx(-75.2921995)
    assert c[1]['referencia'].startswith('PK 15.362')
    assert c[1]['observaciones'].startswith('PK 15.362')
    assert c[2]['fecha'] == '24/08/2026'


def test_hallazgos(informe):
    h = informe['hallazgos']
    assert len(h) == 1
    assert h[0]['abscisa_inicio'] == 385
    assert h[0]['tipo'] == 'Atenuación de corriente'


def test_datos_generales_y_filas_para_el_portal(informe):
    import db
    assert informe['info']['tipo_inspeccion'] == 'CIPS'
    filas = db._puntos_cips_filas('x', informe['cips'])
    assert filas[0]['abscisa'] == 147 and filas[0]['fecha'] == '2026-08-21'
    assert filas[0]['off_limpio'] == pytest.approx(-754.37)
    assert filas[0]['estado'] and filas[2]['estado']


def test_rechaza_un_informe_que_no_es_cips(tmp_path):
    import openpyxl
    p = os.path.join(tmp_path, "x.xlsx")
    openpyxl.Workbook().save(p)
    with pytest.raises(ValueError):
        leer_informe_cips(p)
