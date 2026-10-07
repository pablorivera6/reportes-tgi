"""KMZ de CIPS: como el de PAP (postes + hallazgos + traza), no los ~100.000
puntos del perfil. Antes cada lectura del logger era un placemark y el archivo
quedaba inmanejable en Google Earth."""
import io
import zipfile

import entrega
from cips_adapter import es_poste_cips

BASE = {'cips': [], 'potenciales': [], 'hallazgos': [], 'dcvg_postes': [],
        'dcvg_defectos': [], 'dcvg_hallazgos': [], 'info': {}}


def _cips(n=2000, paso=5):
    pts = []
    for i in range(n):
        a = i * paso
        obs = ''
        if a % 1000 == 0:
            obs = f'pk {a // 1000}+000'                 # marcador de poste
        elif a == 505:
            obs = 'Cruce de vía'
        elif a == 1505:
            obs = 'Poste de potencial sin cables'
        pts.append({'abscisa_val': a, 'lat': 4.5 + a / 1e5, 'lon': -75.7 - a / 1e5,
                    'on_mv': -1500, 'off_mv': -1100, 'on_limpio': -1500, 'off_limpio': -1100,
                    'observaciones': obs})
    return pts


def _kml(kmz):
    z = zipfile.ZipFile(io.BytesIO(kmz))
    return z.read("doc.kml").decode("utf-8")


def _postes(kml):
    """Placemarks de la carpeta Potenciales (los hallazgos pueden usar también
    el icono de poste, p. ej. 'poste sin cables')."""
    if "<Folder><name>Potenciales</name>" not in kml:
        return 0
    return kml.split("<Folder><name>Potenciales</name>")[1].split("</Folder>")[0].count("<Placemark>")


def test_cips_dibuja_postes_y_hallazgos_no_todos_los_puntos():
    data = dict(BASE, info={'tipo_inspeccion': 'CIPS', 'tramo': 'Ramal Salento'}, cips=_cips())
    kmz, motivo = entrega.kmz_de_inspeccion(data)
    assert kmz, motivo
    kml = _kml(kmz)
    # 10 marcadores 'pk N+000' + 1 'poste de potencial' = 11 postes, no 2000 puntos
    assert _postes(kml) == 11, _postes(kml)
    assert kml.count("<Placemark>") < 20
    assert "<LineString>" in kml                      # la traza se conserva
    assert "Cruce" in kml                             # el hallazgo sí
    assert len(kmz) < 60_000                          # liviano


def test_la_traza_del_cips_se_simplifica():
    data = dict(BASE, info={'tipo_inspeccion': 'CIPS'}, cips=_cips(n=20000, paso=1))
    kmz, _ = entrega.kmz_de_inspeccion(data)
    kml = _kml(kmz)
    coords = kml.split("<coordinates>")[1].split("</coordinates>")[0].split()
    assert 2 <= len(coords) <= 3000
    # conserva los extremos
    assert coords[0].startswith("-75.7,4.5") and coords[-1].startswith("-75.89999")


def test_con_postes_del_fastfield_esos_son_los_postes():
    pots = [{'abscisa': i * 1000, 'lat': 4.5 + i / 100, 'lon': -75.7, 'on_mv': -1500,
             'off_mv': -1000} for i in range(5)]
    data = dict(BASE, info={'tipo_inspeccion': 'CIPS'}, cips=_cips(), potenciales=pots)
    kml = _kml(entrega.kmz_de_inspeccion(data)[0])
    assert _postes(kml) == 5


def test_pap_sigue_igual():
    pots = [{'abscisa': i * 1000, 'lat': 4.5 + i / 100, 'lon': -75.7, 'on_mv': -1500,
             'off_mv': -1000} for i in range(7)]
    data = dict(BASE, info={'tipo_inspeccion': 'PAP'}, potenciales=pots,
                hallazgos=[{'abscisa_val': 500, 'lat': 4.505, 'lon': -75.7, 'tipo': 'Cruce',
                            'descripcion': 'Cruce de vía'}])
    kml = _kml(entrega.kmz_de_inspeccion(data)[0])
    assert _postes(kml) == 7 and "Cruce" in kml


def test_es_poste_cips():
    assert es_poste_cips('pk 5+000')
    assert es_poste_cips('PK 002+000 No existe')
    assert es_poste_cips('Poste de potencial sin cables')
    assert not es_poste_cips('Cruce de vía')
    assert not es_poste_cips('')
