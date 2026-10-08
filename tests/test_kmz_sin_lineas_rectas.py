"""El KMZ dibujaba una 'Traza' uniendo los postes con segmentos RECTOS en el
orden de su abscisa. Con PK desordenados o repetidos (Marsella: dos postes en
3+000 y dos en 6+000) la línea cruzaba el mapa en zigzag y el revisor la
confundía con el ducto. Esa línea se quita: entre postes no se dibuja nada.
Solo el CIPS lleva traza, porque sale del GPS real del survey (un vértice cada
25 m), no de unir postes."""
import io
import zipfile

import entrega


def _kml(kmz):
    with zipfile.ZipFile(io.BytesIO(kmz)) as z:
        return z.read("doc.kml").decode("utf-8")


POSTES = [{"lat": 4.972, "lon": -75.777, "abscisa": 3000, "on": -2012, "off": -1792},
          {"lat": 4.965, "lon": -75.783, "abscisa": 2000, "on": -1844, "off": -1379},
          {"lat": 4.961, "lon": -75.777, "abscisa": 3000, "on": -2007, "off": -1341},
          {"lat": 4.944, "lon": -75.745, "abscisa": 7000, "on": -1727, "off": -1127}]


def test_pap_y_dcvg_sin_linea_entre_postes():
    kml = _kml(entrega.construir_kmz("Marsella DCVG", cp_puntos=POSTES,
                                     defectos=[{"lat": 4.96, "lon": -75.78, "abscisa": 4500,
                                                "severidad_pct": 12, "clasificacion": "Muy Pequeño"}]))
    assert "<LineString>" not in kml
    assert "<name>Traza</name>" not in kml
    assert kml.count("<Point>") == 5          # los postes y el defecto siguen ahí


def test_el_cips_conserva_la_traza_del_gps():
    traza = [(4.95 + i * 0.001, -75.77) for i in range(10)]
    kml = _kml(entrega.construir_kmz("CIPS", cp_puntos=POSTES[:2], traza=traza))
    assert kml.count("<LineString>") == 1
    assert "4.959" in kml
