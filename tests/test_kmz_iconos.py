"""Iconos del KMZ por tipo de hallazgo.

TGI usa el catálogo de iconos de Earth Point (números 1-279). La app pintaba
todos los hallazgos con el mismo círculo; ahora cada uno lleva el icono que le
corresponde según lo que reportó la cuadrilla.

Los PNG se incrustan DENTRO del KMZ (`files/…png`), así que el archivo se ve
igual sin conexión a internet.
"""
import io
import zipfile

import pytest

import entrega
from entrega import icono_de_hallazgo


def _kmz(hallazgos):
    return entrega.construir_kmz("Prueba", hallazgos=hallazgos)


def _partes(kmz):
    z = zipfile.ZipFile(io.BytesIO(kmz))
    return z.namelist(), z.read("doc.kml").decode("utf-8")


def _iconos_hallazgo(nombres):
    """PNG de hallazgo incrustados (sin contar el círculo base de los puntos)."""
    return [n for n in nombres
            if n.endswith(".png") and "base_circulo" not in n]


def _h(desc, lat=4.5, lon=-75.7, tipo=""):
    return [{"lat": lat, "lon": lon, "abscisa_val": 100, "tipo": tipo,
             "descripcion": desc}]


# ── Clasificación ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("texto,clave,numero", [
    ("Cruce de vía destapada", "cruce_via", 200),
    ("cruce de caño", "cruce_cano", 231),
    ("cruce de quebrada seca", "cruce_cano", 231),
    ("Cruce de río Cauca", "cruce_cano", 231),
    ("cruce de línea eléctrica de alta tensión", "cruce_linea_electrica", 240),
    ("URPC Balboa", "urpc_propia", 257),
    ("urpc foránea de Cenit", "urpc_foranea", 242),
    ("tubería expuesta en el talud", "tuberia_expuesta", 244),
    ("válvula de derivación", "valvula", 206),
    ("malla de encerramiento", "valvula", 206),
    ("tramo enmontado, sin rocería", "vegetacion", 238),
    ("invasión del DDV con vivienda", "invasion_ddv", 214),
    ("ánodo de sacrificio", "anodo", 271),
    ("tramo aéreo sobre el caño", "tuberia_aerea", 209),
    ("marco H", "marco_h", 207),
    ("terreno removido por excavación", "terreno_removido", 272),
    ("cultivo de café sobre el DDV", "cultivo", 241),
    ("cruce con tubería foránea de Ecopetrol", "cruce_tuberia_foranea", 192),
    ("poste de potencial", "poste_potencial", 177),
])
def test_clasifica_cada_tipo(texto, clave, numero):
    ic = icono_de_hallazgo(texto)
    assert ic is not None, f"{texto!r} no se clasificó"
    assert ic["clave"] == clave
    assert ic["numero"] == numero


def test_derecho_de_via_no_es_cruce_de_via():
    """'derecho de vía' contiene 'vía': la invasión manda sobre el cruce."""
    assert icono_de_hallazgo("invasión del derecho de vía")["clave"] == "invasion_ddv"


def test_tuberia_aerea_gana_a_tuberia_expuesta():
    assert icono_de_hallazgo("tubería aérea expuesta")["clave"] == "tuberia_aerea"


def test_hallazgo_sin_categoria():
    assert icono_de_hallazgo("observación cualquiera del técnico") is None


def test_todos_los_iconos_existen_en_el_proyecto():
    import os
    for ic in entrega.ICONOS_HALLAZGO:
        ruta = entrega.ruta_icono(ic["archivo"])
        assert os.path.exists(ruta), f"falta el PNG de {ic['clave']}: {ic['archivo']}"


# ── KMZ ──────────────────────────────────────────────────────────────────────

def test_el_kmz_incrusta_el_icono_usado():
    nombres, kml = _partes(_kmz(_h("cruce de caño")))
    assert any(n.endswith("231_cruce_cano.png") for n in nombres), nombres
    assert "files/231_cruce_cano.png" in kml       # href relativo, sin internet
    assert "http://maps.google.com" not in kml.split("<Folder>")[-1]


def test_cada_hallazgo_usa_su_estilo():
    nombres, kml = _partes(_kmz(
        _h("cruce de caño") + _h("invasión del DDV", lat=4.6) +
        _h("ánodo de sacrificio", lat=4.7)))
    for clave in ("cruce_cano", "invasion_ddv", "anodo"):
        assert f'<Style id="ic_{clave}">' in kml
        assert f"#ic_{clave}" in kml
    assert len(_iconos_hallazgo(nombres)) == 3


def test_solo_incrusta_los_iconos_que_se_usan():
    nombres, _kml = _partes(_kmz(_h("cruce de caño")))
    pngs = _iconos_hallazgo(nombres)
    assert len(pngs) == 1, f"se incrustaron iconos de más: {pngs}"


def test_hallazgo_sin_categoria_conserva_el_estilo_generico():
    _n, kml = _partes(_kmz(_h("observación cualquiera")))
    assert "#s_Hallazgo" in kml


def test_el_kmz_sigue_siendo_valido_sin_hallazgos():
    kmz = entrega.construir_kmz("Prueba", cp_puntos=[
        {"lat": 4.5, "lon": -75.7, "abscisa": 0, "on": -1500, "off": -1100},
        {"lat": 4.6, "lon": -75.8, "abscisa": 100, "on": -1500, "off": -1100}])
    nombres, kml = _partes(kmz)
    assert "doc.kml" in nombres
    assert "<LineString>" in kml


def test_el_kmz_no_depende_de_internet():
    """Todos los iconos, incluidos los círculos de color, van dentro del KMZ."""
    kmz = entrega.construir_kmz("Prueba",
        cp_puntos=[{"lat": 4.5, "lon": -75.7, "abscisa": 0, "on": -1500, "off": -1100}],
        hallazgos=_h("cruce de caño"))
    nombres, kml = _partes(kmz)
    assert "maps.google.com" not in kml, "quedó un icono apuntando a internet"
    assert any(n.endswith("base_circulo.png") for n in nombres)
