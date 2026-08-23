"""Observaciones de las gráficas del informe DCVG.

La plantilla trae el texto de un informe de ejemplo (Ramal Villa María) en la
celda F32 de 'GRAFICA DCVG' y de 'Gráfica Resistividad'. Si no se reemplaza,
el informe sale con las observaciones de OTRA inspección. Aquí se escribe el
texto de la inspección que se está generando.
"""
import os

import openpyxl

from generator import ReportGenerator, resource_path

VIEJO_DCVG = "Villa María"
VIEJO_RESIST = "94.2%"


def _gen():
    return ReportGenerator(resource_path("DCVG_REP.xlsx"))


def _texto(tmp_path, gen, hoja, nombre="obs.xlsx"):
    out = os.path.join(tmp_path, nombre)
    gen.save(out)
    return str(openpyxl.load_workbook(out)[hoja]["F32"].value or "")


def _postes():
    return [{"tipo": "Poste", "pk_m": 0, "on": -1600.0, "off": -1100.0},
            {"tipo": "Poste", "pk_m": 4000, "on": -1580.0, "off": -1080.0}]


def _defectos(n=3, caracter="AA", ol_re=50.0):
    return [{"pk_m": 500 + i * 1000, "ol_re": ol_re, "caracter": caracter,
             "profundidad": 190} for i in range(n)]


def test_no_queda_texto_del_informe_de_ejemplo(tmp_path):
    gen = _gen()
    gen.fill_observaciones_dcvg({'tramo': 'Ramal Armenia', 'longitud_km': 4},
                                _postes(), _defectos(), [])
    t = _texto(tmp_path, gen, "GRAFICA DCVG")
    assert VIEJO_DCVG not in t
    assert "Ramal Armenia" in t


def test_cuenta_indicaciones_y_densidad(tmp_path):
    gen = _gen()
    # 3 indicaciones en 4 km -> 0,75 indicaciones/km (como el ejemplo)
    gen.fill_observaciones_dcvg({'tramo': 'Ramal Armenia', 'longitud_km': 4},
                                _postes(), _defectos(3), [])
    t = _texto(tmp_path, gen, "GRAFICA DCVG")
    assert "tres (3) indicaciones" in t
    assert "0,75" in t and "Indicaciones/Km" in t


def test_severidad_y_caracter_del_informe(tmp_path):
    gen = _gen()
    # pulso = 500 mV; OL/RE 50 -> 10% (Muy Pequeño, menor a 15%)
    gen.fill_observaciones_dcvg({'tramo': 'Ramal Armenia', 'longitud_km': 4},
                                _postes(), _defectos(3, "AA", 50.0), [])
    t = _texto(tmp_path, gen, "GRAFICA DCVG")
    assert "menor a 15%" in t
    assert "carácter AA" in t


def test_severidades_mezcladas(tmp_path):
    gen = _gen()
    # 50/500=10% (menor a 15) y 250/500=50% (entre 35% y 60%)
    defectos = [{"pk_m": 1000, "ol_re": 50.0, "caracter": "AA"},
                {"pk_m": 2000, "ol_re": 250.0, "caracter": "CC"}]
    gen.fill_observaciones_dcvg({'tramo': 'Ramal Armenia', 'longitud_km': 4},
                                _postes(), defectos, [])
    t = _texto(tmp_path, gen, "GRAFICA DCVG")
    assert "menor a 15%" in t and "entre 35% y 60%" in t
    assert "AA" in t and "CC" in t


def test_sin_defectos_lo_dice(tmp_path):
    gen = _gen()
    gen.fill_observaciones_dcvg({'tramo': 'Ramal Armenia', 'longitud_km': 4},
                                _postes(), [], [])
    t = _texto(tmp_path, gen, "GRAFICA DCVG")
    assert VIEJO_DCVG not in t
    assert "no se identificaron indicaciones" in t.lower()


def test_observaciones_de_resistividad(tmp_path):
    gen = _gen()
    # medidas cada 250 m; R1=3.8 -> rho1 = 2*pi*3.8*100 = 2387 -> Medianamente
    resist = [{"pk_m": 1000 + i * 250, "r1": 3.8, "r2": 2.3, "r3": 2.0}
              for i in range(4)]
    gen.fill_observaciones_dcvg({'tramo': 'Ramal Armenia', 'longitud_km': 4},
                                _postes(), _defectos(), resist)
    t = _texto(tmp_path, gen, "Gráfica Resistividad")
    assert VIEJO_RESIST not in t
    assert "250 m" in t
    assert "1, 2 y 3" in t
    assert "%" in t


def test_sin_resistividades_no_deja_el_texto_viejo(tmp_path):
    gen = _gen()
    gen.fill_observaciones_dcvg({'tramo': 'Ramal Armenia'}, _postes(),
                                _defectos(), [])
    assert VIEJO_RESIST not in _texto(tmp_path, gen, "Gráfica Resistividad")


def test_longitud_desde_las_abscisas_si_no_viene_en_datos_generales(tmp_path):
    gen = _gen()
    # sin longitud_km: la toma del recorrido (0 a 4000 m = 4 km)
    gen.fill_observaciones_dcvg({'tramo': 'Ramal Armenia'}, _postes(),
                                _defectos(3), [])
    t = _texto(tmp_path, gen, "GRAFICA DCVG")
    assert "0,75" in t


def test_una_sola_indicacion_va_en_singular(tmp_path):
    gen = _gen()
    gen.fill_observaciones_dcvg({'tramo': 'La Dorada', 'longitud_km': 12},
                                _postes(), _defectos(1, "CC"), [])
    t = _texto(tmp_path, gen, "GRAFICA DCVG")
    assert "se identificó una (1) indicación" in t
    assert "indicaciones" not in t.split("\n")[0]
    assert "una (1) indicación es de carácter CC" in t


def test_todas_las_indicaciones_llevan_articulo(tmp_path):
    gen = _gen()
    gen.fill_observaciones_dcvg({'tramo': 'Ramal Armenia', 'longitud_km': 4},
                                _postes(), _defectos(3), [])
    t = _texto(tmp_path, gen, "GRAFICA DCVG")
    # como en el texto original de la plantilla
    assert "las tres (3) indicaciones tienen" in t
    assert "las tres (3) indicaciones son de carácter AA" in t
    assert "En el Ramal Armenia" in t
