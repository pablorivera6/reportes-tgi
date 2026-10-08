"""El KMZ dibujaba una 'Traza' uniendo los postes con segmentos RECTOS en el
orden de su abscisa. Con PK desordenados o repetidos (Marsella: dos postes en
3+000 y dos en 6+000) la línea cruzaba el mapa en zigzag y el revisor la
confundía con el ducto. El KMZ queda SOLO con puntos, en los tres tipos: ni la
línea entre postes ni la traza del GPS del survey CIPS (pedido del ingeniero)."""
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


def test_el_cips_tampoco_lleva_linea():
    cips = [dict(abscisa_val=i * 5, lat=4.95 + i * 0.0001, lon=-75.77, on_mv=-1500, off_mv=-1000,
                 off_limpio=-1000, observaciones=('pk 0+000' if i == 0 else '')) for i in range(400)]
    kmz, motivo = entrega.kmz_de_inspeccion({'info': {'tipo_inspeccion': 'CIPS', 'tramo': 'X'},
                                             'cips': cips})
    assert kmz, motivo
    kml = _kml(kmz)
    assert "<LineString>" not in kml and "<name>Traza</name>" not in kml
    assert kml.count("<Point>") >= 1
