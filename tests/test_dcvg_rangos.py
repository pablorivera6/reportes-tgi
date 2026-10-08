"""Gráfica DCVG general: criterios de severidad y eje Y en porcentaje.

Las hojas por rango (~5 km) se retiraron: ver test_dcvg_sin_hojas_por_rango."""
import os

import openpyxl

from generator import ReportGenerator, resource_path


def _datos():
    postes = [{"tipo": "Poste", "pk_m": pk, "on": -1600.0, "off": -1100.0,
               "lat": 4.9, "lon": -75.7} for pk in (136300, 140000, 145000,
               150000, 197325)]
    defectos = [{"pk_m": 142000, "forma_n": 1, "forma_s": 1, "forma_e": 1,
                 "forma_o": 1, "ol_re": 30, "profundidad": 190, "caracter": "CC",
                 "lat": 4.9, "lon": -75.7, "comentarios": "d"}]
    return postes, defectos


def test_graficas_dcvg_criterios_en_porcentaje(tmp_path):
    gen = ReportGenerator(resource_path("DCVG_REP.xlsx"))
    postes, defectos = _datos()
    gen.fill_dcvg(postes, defectos)
    n = sum(1 for x in postes + defectos if x.get('pk_m') is not None)
    gen.fill_graficas_dcvg(n, 0)
    out = os.path.join(tmp_path, "g.xlsx")
    gen.save(out)
    ws = openpyxl.load_workbook(out)["GRAFICA DCVG"]
    # criterios como fracción (no 15/35/60)
    assert ws.cell(row=39, column=5).value == 0.15
    assert ws.cell(row=39, column=6).value == 0.35
    assert ws.cell(row=39, column=7).value == 0.6
    # eje Y en porcentaje
    assert ws._charts[0].y_axis.numFmt.formatCode == '0%'


def test_eje_y_de_severidad_va_de_0_a_100_por_ciento(tmp_path):
    """La severidad %IR se escribe en fracción (0..1). La plantilla traía el
    eje Y en 0..100 (de cuando iba en porcentaje) y la gráfica llegaba al
    10000 %: el máximo va en 1,0 = 100 %, con unidades 0,1 y 0,02 (como lo
    ajusta el ingeniero en Excel)."""
    gen = ReportGenerator(resource_path("DCVG_REP.xlsx"))
    postes, defectos = _datos()
    gen.fill_dcvg(postes, defectos)
    gen.fill_graficas_dcvg(gen.dcvg_filas, 0)
    out = os.path.join(tmp_path, "y.xlsx")
    gen.save(out)
    eje = openpyxl.load_workbook(out)["GRAFICA DCVG"]._charts[0].y_axis
    assert eje.scaling.min == 0
    assert eje.scaling.max == 1.0
    assert eje.majorUnit == 0.1
    assert eje.minorUnit == 0.02
