"""Puntos de potencial (postes) en el KMZ: icono 177 del catálogo de TGI.

Antes se dibujaban como círculo de color según el estado de protección. Ahora
llevan el icono de poste; el estado queda en el nombre y en la ficha del punto.
"""
import io
import zipfile

import entrega


def _kmz(**kw):
    return entrega.construir_kmz("Prueba", **kw)


def _partes(kmz):
    z = zipfile.ZipFile(io.BytesIO(kmz))
    return z.namelist(), z.read("doc.kml").decode("utf-8")


CP = [{"lat": 4.5, "lon": -75.7, "abscisa": 0, "on": -1600, "off": -1100},
      {"lat": 4.6, "lon": -75.8, "abscisa": 100, "on": -1600, "off": -700},
      {"lat": 4.7, "lon": -75.9, "abscisa": 200, "on": -1600, "off": -1300}]


def test_los_postes_usan_el_icono_177():
    nombres, kml = _partes(_kmz(cp_puntos=CP))
    assert any(n.endswith("177_poste_potencial.png") for n in nombres), nombres
    assert '<Style id="ic_poste">' in kml
    assert kml.count("#ic_poste") == len(CP)


def test_el_estado_de_proteccion_no_se_pierde():
    """Ya no se ve por color, así que tiene que estar en el texto."""
    _n, kml = _partes(_kmz(cp_puntos=CP))
    for estado in ("Protegido", "Desprotegido", "Sobreprotegido"):
        assert estado in kml, f"falta el estado {estado}"


def test_el_estado_va_en_el_nombre_del_punto():
    _n, kml = _partes(_kmz(cp_puntos=CP))
    assert "· Desprotegido</name>" in kml
    assert "· Protegido</name>" in kml


def test_la_traza_se_conserva():
    _n, kml = _partes(_kmz(cp_puntos=CP))
    assert "<LineString>" in kml


def test_sigue_sin_depender_de_internet():
    _n, kml = _partes(_kmz(cp_puntos=CP))
    assert "maps.google.com" not in kml
