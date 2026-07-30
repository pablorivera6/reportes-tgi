"""Un survey CIPS con MÁS puntos que la capacidad de la hoja (bloque de firmas
al final) no debe tronar con 'MergedCell is read-only': fill_cips escribe hasta
la capacidad, avisa cuántos recortó (cips_truncados) y deja el bloque de firmas
intacto. Caso real: OCENSA El Porvenir–Miraflores (survey muy largo)."""
import openpyxl

from generator import ReportGenerator, resource_path


def _capacidad(ws):
    firmas = next((r for r in range(12, ws.max_row + 1)
                   if ws.cell(row=r, column=3).value == 'ELABORÓ'), None)
    resumen = min([m.min_row for m in ws.merged_cells.ranges
                   if m.min_row >= 12] + [firmas])
    return resumen - 12, firmas


def test_survey_gigante_no_truena_y_avisa():
    gen = ReportGenerator(resource_path("CIPS EN BLANCO.xlsx"))
    cap, fila_firmas = _capacidad(gen.wb['Potenciales CIPS'])
    n = cap + 5
    datos = [{'abscisa_val': i, 'on_mv': -1100.0, 'off_mv': -900.0,
              'on_limpio': -1100.0, 'off_limpio': -900.0} for i in range(n)]
    gen.fill_cips(datos)   # no debe lanzar excepción
    ws = gen.wb['Potenciales CIPS']
    assert gen.cips_truncados == 5
    # el bloque de firmas sigue intacto
    assert ws.cell(row=fila_firmas, column=3).value == 'ELABORÓ'
    # la última fila de datos permitida tiene el potencial escrito
    assert ws.cell(row=12 + cap - 1, column=5).value == -1100.0


def test_survey_normal_no_recorta():
    gen = ReportGenerator(resource_path("CIPS EN BLANCO.xlsx"))
    datos = [{'abscisa_val': i * 5, 'on_mv': -1100.0, 'off_mv': -900.0,
              'on_limpio': -1100.0, 'off_limpio': -900.0} for i in range(50)]
    gen.fill_cips(datos)
    assert gen.cips_truncados == 0
