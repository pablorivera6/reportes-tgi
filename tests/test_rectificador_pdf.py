"""PDF de un rectificador: los hallazgos y las mediciones de campo que no
caben en la tabla de operación viajan en `obs` y deben verse completos."""
import io

from pypdf import PdfReader

import rectificadores as rx

_LARGO = ("Hallazgo: fusibles DC del positivo (ánodos) y del negativo "
          "(estructura) puenteados con alambre. Recomendación: reponer los "
          "fusibles con la capacidad nominal y retirar los puentes.")


def _texto(pdf):
    t = " ".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf)).pages)
    return " ".join(t.split())


def _rect(obs):
    return {"plant": "DISTRITO 4", "placa": {"TAG": "Granada"}, "nominales": {},
            "op_data": {"data": [{"fecha": "21/09/2026", "vac": "122.8",
                                  "vdc": "15.86", "idc": "1.28"}]},
            "obs": obs}


def test_pdf_muestra_observaciones():
    t = _texto(rx.pdf_rectificador(_rect("Horómetro DC: 4343.40 h\n" + _LARGO)))
    assert "OBSERVACIONES" in t
    assert "4343.40" in t


def test_linea_larga_se_parte_sin_perder_texto():
    t = _texto(rx.pdf_rectificador(_rect(_LARGO)))
    assert "puenteados con alambre" in t
    assert "retirar los puentes" in t          # el final de la línea no se corta


def test_pdf_sin_observaciones_no_rompe():
    rect = {"placa": {"TAG": "X"}, "op_data": {"data": []}}
    assert "OBSERVACIONES" not in _texto(rx.pdf_rectificador(rect))


def test_lineas_de_observacion():
    assert rx.lineas_obs({"obs": " a \n\n b "}) == ["a", "b"]
    assert rx.lineas_obs({}) == []


def test_diagnostico_no_contradice_los_hallazgos():
    # Sin alertas automáticas pero con hallazgos: no decir "sin necesidades".
    t = _texto(rx.pdf_rectificador(_rect(_LARGO)))
    assert "Sin necesidades críticas" not in t
    assert "Ver observaciones" in t
    sin = _texto(rx.pdf_rectificador({"placa": {"TAG": "X"}, "op_data": {"data": []}}))
    assert "Sin necesidades críticas" in sin


def test_muchas_lineas_entran_todas():
    # 12 hallazgos de 2 renglones = 24 renglones: más de los 17 que caben a
    # tamaño normal. Se compacta; ninguno se pierde.
    obs = "\n".join(f"Hallazgo {i:02d}: " + _LARGO for i in range(12))
    t = _texto(rx.pdf_rectificador(_rect(obs)))
    for i in range(12):
        assert f"Hallazgo {i:02d}:" in t, i
    assert t.count("retirar los puentes") == 12


def test_si_de_verdad_no_cabe_lo_avisa():
    obs = "\n".join(f"Hallazgo {i:02d}: " + _LARGO for i in range(40))
    t = _texto(rx.pdf_rectificador(_rect(obs)))
    assert "ver el detalle completo en el portal" in t
