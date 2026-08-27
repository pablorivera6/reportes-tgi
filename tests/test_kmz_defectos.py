"""Defectos DCVG en el KMZ: triángulo (icono 205) coloreado por carácter.

  Rojo    = AA (anódico-anódico)
  Amarillo = CA (catódico-anódico)
  Azul    = CC (catódico-catódico)

Antes los defectos se pintaban con el círculo de color de la severidad. La
severidad y la clasificación siguen estando en el nombre y en la ficha del
punto, así que no se pierde información.
"""
import io
import zipfile

import pytest

import entrega

# KML usa aabbggrr, no rrggbb
ROJO, AMARILLO, AZUL = "ff0000ff", "ff00ffff", "ffff0000"


def _kmz(defectos):
    return entrega.construir_kmz("Prueba", defectos=defectos)


def _partes(kmz):
    z = zipfile.ZipFile(io.BytesIO(kmz))
    return z.namelist(), z.read("doc.kml").decode("utf-8")


def _d(caracter, lat=4.5, **kw):
    base = {"lat": lat, "lon": -75.7, "abscisa": 1500, "severidad_pct": 19.1,
            "clasificacion": "Pequeño", "caracter": caracter}
    base.update(kw)
    return base


@pytest.mark.parametrize("caracter,color", [
    ("AA", ROJO), ("CA", AMARILLO), ("CC", AZUL),
])
def test_color_por_caracter(caracter, color):
    nombres, kml = _partes(_kmz([_d(caracter)]))
    assert f'<Style id="def_{caracter}">' in kml
    assert f"<color>{color}</color>" in kml
    assert f"#def_{caracter}" in kml


def test_usa_el_triangulo_incrustado():
    nombres, kml = _partes(_kmz([_d("AA")]))
    assert any(n.endswith("205_defecto.png") for n in nombres), nombres
    assert "files/205_defecto.png" in kml
    assert "maps.google.com" not in kml


def test_los_tres_caracteres_conviven():
    _n, kml = _partes(_kmz([_d("AA"), _d("CA", lat=4.6), _d("CC", lat=4.7)]))
    for c, color in (("AA", ROJO), ("CA", AMARILLO), ("CC", AZUL)):
        assert f'<Style id="def_{c}">' in kml
        assert f"#def_{c}" in kml
    assert kml.count("<Placemark>") == 3


def test_conserva_severidad_y_clasificacion_en_la_ficha():
    _n, kml = _partes(_kmz([_d("CC")]))
    assert "19.1" in kml and "Pequeño" in kml


def test_el_caracter_va_en_el_nombre_del_punto():
    _n, kml = _partes(_kmz([_d("CA")]))
    assert "<name>Defecto CA" in kml


def test_defecto_sin_caracter_usa_la_severidad():
    """Si el técnico no registró el carácter, se conserva el color por
    clasificación de siempre."""
    _n, kml = _partes(_kmz([_d("", clasificacion="Grande")]))
    assert "#s_Grande" in kml
    assert '<Style id="def_' not in kml


def test_caracter_en_minusculas_o_con_espacios():
    for escrito in ("aa", " AA ", "Aa"):
        _n, kml = _partes(_kmz([_d(escrito)]))
        assert "#def_AA" in kml, f"no reconoció el carácter {escrito!r}"
