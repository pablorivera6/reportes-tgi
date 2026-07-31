"""Fase 2 DCVG: hojas por rango (~5 km) = zoom de la gráfica DCVG por segmento."""
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


def test_rangos_dcvg_crea_hojas_por_segmento(tmp_path):
    gen = ReportGenerator(resource_path("DCVG_REP.xlsx"))
    postes, defectos = _datos()
    gen.fill_dcvg(postes, defectos)
    hojas = gen.fill_rangos_dcvg(postes, defectos)
    out = os.path.join(tmp_path, "d.xlsx")
    gen.save(out)
    wb = openpyxl.load_workbook(out)
    rangos = [n for n in wb.sheetnames if n.startswith("K ")]
    # extensión 136300..197325 -> primer parcial + bloques de 5km
    assert len(rangos) >= 2
    assert any("136+300" in n for n in rangos)
    assert any("197+325" in n or "195+000" in n for n in rangos)
    # cada hoja de rango tiene una gráfica con eje X del segmento
    prim = next(n for n in rangos if "136+300" in n)
    ch = wb[prim]._charts[0]
    assert ch.x_axis.scaling.min == 136300
    assert ch.x_axis.scaling.max < 141000   # limitado al primer segmento
    # las series de datos siguen apuntando a Inspección DCVG
    refs = [s.yVal.numRef.f for s in ch.series if s.yVal and s.yVal.numRef]
    assert any("Inspección DCVG" in str(f) for f in refs)


def test_rangos_dcvg_sin_datos_no_rompe():
    gen = ReportGenerator(resource_path("DCVG_REP.xlsx"))
    assert gen.fill_rangos_dcvg([], []) == 0
