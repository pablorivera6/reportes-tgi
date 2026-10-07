"""El FastField PAP trae la columna 'Cliente' (= 'TGI'). El lector la escribía
en `contrato`, así que el informe y el nombre del archivo salían con 'TGI'
en vez del número de contrato."""
import openpyxl

from readers import FastFieldReader


def _fastfield_pap(path, cliente="TGI", contrato=None):
    wb = openpyxl.Workbook()
    root = wb.active
    root.title = "Root"
    root.append(["a", "b", "c", "d", "e", "f", "Técnico", "h", "Fecha"])
    root.append(["", "", "", "", "", "", "Juan Perez", "", "09-27-2026"])
    ws = wb.create_sheet("subform_1")
    enc = ["Cliente", "Tramo TGI", "Abscisado", "Localizacion GPS",
           "Referencia Geografica", "ON [mV]", "OFF [mV]", "Observaciones"]
    fila = [cliente, "Ramal Salento", "0+100", "4.63,-75.57",
            "Poste de Potencial", -1200, -1000, ""]
    if contrato is not None:
        enc.insert(1, "Contrato")
        fila.insert(1, contrato)
    ws.append(enc)
    ws.append(fila)
    wb.save(path)
    return path


def test_cliente_no_es_el_contrato(tmp_path):
    d = FastFieldReader().read(_fastfield_pap(tmp_path / "ff.xlsx"))
    assert d["contrato"] == ""
    assert d["cliente"] == "TGI"
    assert d["tramo"] == "Ramal Salento"
    assert len(d["potenciales"]) == 1


def test_una_columna_contrato_si_se_lee(tmp_path):
    d = FastFieldReader().read(_fastfield_pap(tmp_path / "ff.xlsx", contrato="551007370"))
    assert d["contrato"] == "551007370"
    assert d["cliente"] == "TGI"
