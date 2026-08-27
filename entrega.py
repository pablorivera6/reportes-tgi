"""Paquete de entrega TGI (numeral 6.3.5) + exportación de KMZ de la inspección.

La idea clave: las CASILLAS del formulario del técnico ya definen la estructura
de carpetas del entregable. Cada categoría de archivo tiene asignada su carpeta
del contrato, así el paquete se arma solo con lo que subió el técnico + el
informe/PPM generados + el KMZ.

Estructura del entregable (6.3.5):
  01_Anexo_Huellas_Osciloscopicas · 02_Anexo_GPS · 03_Data_Logger ·
  04_Anexos (informe + KMZ) · 05_PPM · 06_RF (registro fotográfico)
"""
from __future__ import annotations

import io
import os
import zipfile
from xml.sax.saxutils import escape

from dashboard import estado_cp, COLOR_ESTADO

# ── Carpetas del entregable ──────────────────────────────────────────────────
FOLDERS = {
    "huellas_osc": "01_Anexo_Huellas_Osciloscopicas",
    "gps":         "02_Anexo_GPS",
    "logger":      "03_Data_Logger",
    "anexos":      "04_Anexos",
    "ppm":         "05_PPM",
    "rf":          "06_RF",
}

_XLS = ["xlsx", "xls"]
_IMG = ["jpg", "jpeg", "png", "heic"]
_CRUDO = ["xlsx", "xls", "csv", "txt"]


def _c(clave, etiqueta, req, tipos, carpeta, grupo, sub=None):
    return {"clave": clave, "etiqueta": etiqueta, "req": req, "tipos": tipos,
            "carpeta": carpeta, "grupo": grupo, "sub": sub}


# Crudos para el dossier (comunes a todas las inspecciones)
_CRUDOS = [
    _c("huellas_osc", "Huellas osciloscópicas (crudo del logger, editable)",
       False, _CRUDO, "huellas_osc", "crudo"),
]

# Anexos de inspecciones adicionales (van a 04_Anexos en su subcarpeta).
# Comunes a todos los tipos porque la inspección visual de interfases se pide
# junto con CIPS/PAP/DCVG del mismo tramo.
_ANEXOS_COMUNES = [
    _c("anexo_interfases", "Inspección Visual de Interfases (FastField)",
       False, _IMG, "anexos", "anexo", "Inspeccion_Visual_Interfases"),
]

# Registro fotográfico (mín. 5 fotos por elemento, en orden de abscisado)
_RF_COMUNES = [
    _c("foto_postes", "Fotos — postes de medición", False, _IMG, "rf", "rf", "Postes"),
    _c("foto_interfases", "Fotos — interfases aéreo/enterrado", False, _IMG, "rf", "rf", "Interfases"),
    _c("foto_hallazgos", "Fotos — hallazgos / cruces", False, _IMG, "rf", "rf", "Hallazgos"),
    _c("foto_general", "Fotos — panorámicas generales", False, _IMG, "rf", "rf", "Panoramicas"),
]

# Catálogo de casillas por tipo de inspección
CATALOGO = {
    "CIPS": [
        _c("cips", "Archivo CIPS (iBTVM)", True, _XLS, "logger", "proc"),
    ] + _CRUDOS + _ANEXOS_COMUNES + _RF_COMUNES,
    "PAP": [
        _c("fastfield_pap", "Potenciales PAP (FastField)", True, _XLS, "anexos", "proc"),
        _c("equipos", "Listado de equipos (opcional)", False, _XLS, "anexos", "proc"),
        _c("rectificador", "Rectificador URPC (opcional)", False, _XLS, "anexos", "proc"),
        _c("aislamientos", "Aislamientos FastField (opcional)", False, _XLS, "anexos", "proc"),
    ] + _CRUDOS + [
        _c("foto_rectificadores", "Fotos — rectificadores", False, _IMG, "rf", "rf", "Rectificadores"),
    ] + _ANEXOS_COMUNES + _RF_COMUNES,
    "DCVG": [
        _c("dcvg", "FastField DCVG", True, _XLS, "anexos", "proc"),
        _c("resistividades", "Resistividades", True, _XLS, "anexos", "proc"),
        _c("logger", "Data cruda del logger (hallazgos)", True, _XLS, "logger", "proc"),
    ] + _CRUDOS + [
        _c("foto_defectos", "Fotos — defectos DCVG", False, _IMG, "rf", "rf", "Defectos"),
    ] + _ANEXOS_COMUNES + _RF_COMUNES,
}


def _cat_por_clave(tipo):
    return {c["clave"]: c for c in CATALOGO.get(tipo, [])}


# ── Iconos del KMZ por tipo de hallazgo ──────────────────────────────────────
# Números del catálogo de iconos de Earth Point (el que usa TGI, 1-279). Los
# PNG viven en `iconos_kml/` y se incrustan DENTRO del KMZ, así que el archivo
# se ve igual sin conexión a internet.
#
# El orden IMPORTA: se evalúa de arriba abajo y gana el primero que case, así
# que lo específico va antes que lo genérico ('derecho de vía' es invasión, no
# cruce de vía; 'tubería aérea expuesta' es aérea, no expuesta).
ICONOS_HALLAZGO = (
    {"clave": "invasion_ddv", "numero": 214, "archivo": "214_invasion_ddv.png",
     "nombre": "Invasión DDV",
     "patrones": (r"invasi",)},
    {"clave": "marco_h", "numero": 207, "archivo": "207_marco_h.png",
     "nombre": "Marco H", "patrones": (r"marco\s*h\b",)},
    {"clave": "anodo", "numero": 271, "archivo": "271_anodo.png",
     "nombre": "Ánodo", "patrones": (r"[áa]nodo",)},
    {"clave": "urpc_foranea", "numero": 242, "archivo": "242_urpc_foranea.png",
     "nombre": "URPC foránea",
     "patrones": (r"(urpc|rectificador)[^.]{0,30}for[áa]nea",
                  r"for[áa]nea[^.]{0,30}(urpc|rectificador)")},
    {"clave": "urpc_propia", "numero": 257, "archivo": "257_urpc_propia.png",
     "nombre": "URPC propia", "patrones": (r"\burpc\b", r"rectificador")},
    {"clave": "cruce_tuberia_foranea", "numero": 192,
     "archivo": "192_cruce_tuberia_foranea.png", "nombre": "Cruce de tubería foránea",
     "patrones": (r"(tuber[íi]a|l[íi]nea|ducto)[^.]{0,30}for[áa]nea",
                  r"for[áa]nea[^.]{0,30}(tuber[íi]a|ducto)")},
    {"clave": "cruce_linea_electrica", "numero": 240,
     "archivo": "240_cruce_linea_electrica.png", "nombre": "Cruce de línea eléctrica",
     "patrones": (r"l[íi]nea[^.]{0,20}el[ée]ctrica", r"el[ée]ctrica",
                  r"(alta|media|baja)\s+tensi[óo]n", r"torre\s+de\s+energ")},
    {"clave": "tuberia_aerea", "numero": 209, "archivo": "209_tuberia_aerea.png",
     "nombre": "Tubería aérea", "patrones": (r"a[ée]re[oa]", r"aerio")},
    {"clave": "cruce_cano", "numero": 231, "archivo": "231_cruce_cano.png",
     "nombre": "Cruce de caño/quebrada/río",
     "patrones": (r"ca[ñn]o", r"quebrada", r"\br[íi]o\b", r"arroyo",
                  r"humedal", r"laguna")},
    {"clave": "tuberia_expuesta", "numero": 244, "archivo": "244_tuberia_expuesta.png",
     "nombre": "Tubería expuesta",
     "patrones": (r"expuest", r"descubiert", r"aflorad")},
    {"clave": "valvula", "numero": 206, "archivo": "206_valvula.png",
     "nombre": "Válvula / Derivación / Enmallado",
     "patrones": (r"v[áa]lvula", r"derivaci[óo]n", r"enmallad", r"\bmalla\b",
                  r"encerramiento", r"enseramiento")},
    {"clave": "vegetacion", "numero": 238, "archivo": "238_vegetacion.png",
     "nombre": "Vegetación espesa o tramo sin rocería",
     "patrones": (r"roce[rn][íi]a", r"enmontad", r"montad[oa]", r"maleza",
                  r"vegetaci[óo]n", r"rastrojo", r"sin\s+paso", r"\bsalto\b")},
    {"clave": "terreno_removido", "numero": 272, "archivo": "272_terreno_removido.png",
     "nombre": "Terreno removido",
     "patrones": (r"terreno\s+removido", r"remoci[óo]n", r"excavaci[óo]n",
                  r"movimiento\s+de\s+tierra", r"derrumbe", r"deslizamiento")},
    {"clave": "cultivo", "numero": 241, "archivo": "241_cultivo.png",
     "nombre": "Cultivo", "patrones": (r"cultivo", r"sembrad", r"siembra",
                                       r"plataci|plantaci[óo]n")},
    {"clave": "cruce_via", "numero": 200, "archivo": "200_cruce_via.png",
     "nombre": "Cruce de vía",
     "patrones": (r"(?<!derecho de )\bv[íi]a\b", r"carretera",
                  r"carreteable", r"camino")},
    {"clave": "poste_potencial", "numero": 177, "archivo": "177_poste_potencial.png",
     "nombre": "Poste de potencial", "patrones": (r"poste",)},
)

CARPETA_ICONOS = "iconos_kml"
ICONO_BASE = "base_circulo.png"   # círculo de color de los puntos

# Defectos DCVG: triángulo (icono 205 del catálogo de TGI) teñido según el
# carácter de la indicación. KML usa aabbggrr, no rrggbb.
ICONO_DEFECTO = "205_defecto.png"
COLOR_CARACTER = {"AA": "ff0000ff",     # rojo
                  "CA": "ff00ffff",     # amarillo
                  "CC": "ffff0000"}     # azul


def ruta_icono(archivo):
    """Ruta al PNG del icono dentro del proyecto."""
    from generator import resource_path
    return resource_path(os.path.join(CARPETA_ICONOS, archivo))


def icono_de_hallazgo(texto, tipo=""):
    """Icono que le corresponde a un hallazgo según lo que reportó la cuadrilla.
    Devuelve el dict del catálogo, o None si no encaja en ninguna categoría."""
    import re as _re
    import unicodedata as _ud
    crudo = f"{tipo} {texto}".strip()
    plano = ''.join(c for c in _ud.normalize('NFD', crudo)
                    if _ud.category(c) != 'Mn').lower()
    for ic in ICONOS_HALLAZGO:
        for patron in ic["patrones"]:
            # los patrones traen tildes opcionales; se comparan contra el texto
            # sin tildes y contra el original, para aceptar ambas escrituras
            if _re.search(patron, plano, _re.IGNORECASE) or \
               _re.search(patron, crudo.lower(), _re.IGNORECASE):
                return ic
    return None


# ── KMZ de la inspección ─────────────────────────────────────────────────────
_KML_COLOR = {                       # KML usa aabbggrr
    "Protegido": "ff4a7a1a", "Desprotegido": "ff3a11c7",
    "Sobreprotegido": "ffeb6f1f", "Sin dato": "ff9ca39c",
    "Muy Pequeño": "ff4a7a1a", "Pequeño": "ff4cb884",
    "Mediano": "ff0b9ef5", "Grande": "ff3a11c7",
    "Hallazgo": "ff00ffff",
}


def _placemark(nombre, lat, lon, estilo, desc=""):
    d = f"<description>{escape(desc)}</description>" if desc else ""
    return (f'<Placemark><name>{escape(str(nombre))}</name>{d}'
            f'<styleUrl>#{estilo}</styleUrl>'
            f'<Point><coordinates>{lon},{lat},0</coordinates></Point></Placemark>')


def kmz_de_inspeccion(data):
    """KMZ de la inspección que está en memoria. Devuelve (bytes, motivo).

    `motivo` explica por qué NO se pudo armar, en vez de fallar en silencio:
    antes cualquier problema aquí hacía desaparecer de la pantalla tanto el KMZ
    como el paquete de entrega.

    Toma los puntos según el tipo: CIPS/PAP de las lecturas; DCVG de los postes
    (la traza) más los defectos por severidad. Los hallazgos entran siempre,
    haya o no defectos.
    """
    try:
        from cips_adapter import cips_a_hallazgos
        info = (data or {}).get('info') or {}
        tipo = info.get('tipo_inspeccion', '')
        cp, defectos, hall = [], [], []

        if data.get('cips'):
            for c in data['cips']:
                off = c.get('off_limpio') if c.get('off_limpio') is not None else c.get('off_mv')
                on = c.get('on_limpio') if c.get('on_limpio') is not None else c.get('on_mv')
                cp.append({'lat': c.get('lat'), 'lon': c.get('lon'),
                           'abscisa': c.get('abscisa_val'), 'on': on, 'off': off})
            hall = cips_a_hallazgos(data['cips'])
        elif data.get('potenciales'):
            for p in data['potenciales']:
                cp.append({'lat': p.get('lat'), 'lon': p.get('lon'),
                           'abscisa': (p.get('abscisa') if p.get('abscisa') is not None
                                       else p.get('pk_m')),
                           'on': p.get('on_mv') or p.get('on'),
                           'off': p.get('off_mv') or p.get('off')})
            hall = data.get('hallazgos') or []

        # DCVG: los postes dan la traza aunque los defectos no traigan GPS
        if data.get('dcvg_postes'):
            for p in data['dcvg_postes']:
                cp.append({'lat': p.get('lat'), 'lon': p.get('lon'),
                           'abscisa': p.get('pk_m'),
                           'on': p.get('on'), 'off': p.get('off')})
        if data.get('dcvg_defectos'):
            from db import _severidad_dcvg
            sev = _severidad_dcvg(data.get('dcvg_postes') or [], data['dcvg_defectos'])
            for d, s in zip(data['dcvg_defectos'], sev):
                defectos.append({'lat': d.get('lat'), 'lon': d.get('lon'),
                                 'abscisa': d.get('pk_m'),
                                 'severidad_pct': s['severidad_pct'],
                                 'clasificacion': s['clasificacion']})
        # los hallazgos del logger entran haya o no defectos
        if data.get('dcvg_hallazgos'):
            hall = cips_a_hallazgos(data['dcvg_hallazgos'])

        con_gps = [x for x in (cp + defectos + list(hall or []))
                   if x.get('lat') is not None and x.get('lon') is not None]
        if not con_gps:
            return (None, "Ningún punto de la inspección tiene coordenadas GPS, "
                          "así que no hay nada que dibujar en el mapa.")
        nombre = f"{info.get('tramo', '')} {tipo}".strip() or "Inspección TGI"
        return (construir_kmz(nombre, cp_puntos=cp, defectos=defectos,
                              hallazgos=hall), "")
    except Exception as e:
        return (None, f"No se pudo armar el KMZ: {type(e).__name__}: {e}")


def construir_kmz(nombre_doc, cp_puntos=None, defectos=None, hallazgos=None) -> bytes:
    """Construye un KMZ (KML comprimido) con la traza, los puntos coloreados por
    estado (CIPS/PAP), los defectos DCVG por severidad y los hallazgos."""
    # círculo base de los puntos por estado/severidad: también va dentro del
    # KMZ, para que el archivo no dependa de internet en ningún punto
    _base = ruta_icono(ICONO_BASE)
    _href_base = (f'files/{ICONO_BASE}' if os.path.exists(_base)
                  else 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png')
    estilos = "".join(
        f'<Style id="s_{k}"><IconStyle><color>{v}</color><scale>0.7</scale>'
        f'<Icon><href>{_href_base}</href></Icon>'
        f'</IconStyle></Style>' for k, v in _KML_COLOR.items())
    estilos += ('<Style id="s_linea"><LineStyle><color>ff8a8a8a</color>'
                '<width>2</width></LineStyle></Style>')

    cuerpo = []
    iconos_usados = {}      # clave -> icono; se incrustan al final en el KMZ
    caracteres_usados = set()   # AA/CA/CC de los defectos dibujados
    cp = [p for p in (cp_puntos or []) if p.get("lat") is not None and p.get("lon") is not None]
    # traza (línea por los puntos ordenados por abscisa)
    if len(cp) >= 2:
        orden = sorted(cp, key=lambda p: p.get("abscisa") or 0)
        coords = " ".join(f"{p['lon']},{p['lat']},0" for p in orden)
        cuerpo.append(f'<Placemark><name>Traza</name><styleUrl>#s_linea</styleUrl>'
                      f'<LineString><coordinates>{coords}</coordinates></LineString></Placemark>')
    # puntos CP por estado
    car_cp = []
    for p in cp:
        est = p.get("estado") or estado_cp(p.get("off"))
        desc = (f"Abscisa: {_absc(p.get('abscisa'))}\nON: {p.get('on')} mV\n"
                f"OFF: {p.get('off')} mV\nEstado: {est}")
        car_cp.append(_placemark(_absc(p.get("abscisa")), p["lat"], p["lon"],
                                 f"s_{est}", desc))
    if car_cp:
        cuerpo.append(f'<Folder><name>Potenciales</name>{"".join(car_cp)}</Folder>')
    # defectos DCVG
    car_def = []
    for d in (defectos or []):
        if d.get("lat") is None or d.get("lon") is None:
            continue
        clas = d.get("clasificacion") or "Sin dato"
        car = str(d.get("caracter") or "").strip().upper()
        desc = (f"Abscisa: {_absc(d.get('abscisa'))}\nCarácter: {car or '—'}"
                f"\nSeveridad %IR: {d.get('severidad_pct')}"
                f"\nClasificación: {clas}")
        # triángulo teñido por carácter (AA rojo · CA amarillo · CC azul); si el
        # técnico no registró el carácter, se conserva el color por severidad
        if car in COLOR_CARACTER:
            caracteres_usados.add(car)
            estilo_d = f"def_{car}"
            etiqueta_d = f"Defecto {car}"
        else:
            estilo_d, etiqueta_d = f"s_{clas}", "Defecto"
        car_def.append(_placemark(f"{etiqueta_d} {_absc(d.get('abscisa'))}",
                                  d["lat"], d["lon"], estilo_d, desc))
    if car_def:
        cuerpo.append(f'<Folder><name>Defectos DCVG</name>{"".join(car_def)}</Folder>')
    # hallazgos
    car_h = []
    for h in (hallazgos or []):
        la = h.get("lat") if h.get("lat") is not None else h.get("lat_ini")
        lo = h.get("lon") if h.get("lon") is not None else h.get("lon_ini")
        if la is None or lo is None:
            continue
        abv = h.get("abscisa_val") if h.get("abscisa_val") is not None else h.get("abscisa_ini")
        desc = f"{h.get('tipo','')}\n{h.get('descripcion','')}"
        # icono según lo que reportó la cuadrilla (catálogo de TGI)
        ic = icono_de_hallazgo(h.get('descripcion') or h.get('observaciones') or '',
                               h.get('tipo', ''))
        if ic:
            iconos_usados[ic["clave"]] = ic
            estilo, etiqueta = f"ic_{ic['clave']}", ic["nombre"]
        else:
            estilo, etiqueta = "s_Hallazgo", h.get('tipo', 'Hallazgo')
        car_h.append(_placemark(f"{etiqueta} {_absc(abv)}", la, lo, estilo, desc))
    if car_h:
        cuerpo.append(f'<Folder><name>Hallazgos</name>{"".join(car_h)}</Folder>')

    # un estilo por icono usado, apuntando al PNG que va DENTRO del KMZ
    incrustar = {}
    if os.path.exists(_base):
        incrustar[f'files/{ICONO_BASE}'] = _base

    # defectos DCVG: un estilo por carácter, con el triángulo teñido
    if caracteres_usados:
        _tri = ruta_icono(ICONO_DEFECTO)
        _href_tri = (f'files/{ICONO_DEFECTO}' if os.path.exists(_tri)
                     else 'http://maps.google.com/mapfiles/kml/shapes/triangle.png')
        if os.path.exists(_tri):
            incrustar[f'files/{ICONO_DEFECTO}'] = _tri
        for car in sorted(caracteres_usados):
            estilos += (f'<Style id="def_{car}"><IconStyle>'
                        f'<color>{COLOR_CARACTER[car]}</color><scale>1.1</scale>'
                        f'<Icon><href>{_href_tri}</href></Icon></IconStyle></Style>')
    for clave, ic in iconos_usados.items():
        ruta = ruta_icono(ic["archivo"])
        if os.path.exists(ruta):
            href = f'files/{ic["archivo"]}'
            incrustar[href] = ruta
        else:   # respaldo: el icono público de Google
            href = f'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'
        estilos += (f'<Style id="ic_{clave}"><IconStyle><scale>1.1</scale>'
                    f'<Icon><href>{href}</href></Icon></IconStyle></Style>')

    kml = (f'<?xml version="1.0" encoding="UTF-8"?>'
           f'<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
           f'<name>{escape(nombre_doc)}</name>{estilos}{"".join(cuerpo)}'
           f'</Document></kml>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml)
        for href, ruta in incrustar.items():
            with open(ruta, "rb") as f:
                z.writestr(href, f.read())
    return buf.getvalue()


def _absc(v):
    try:
        v = int(v)
        return f"K {v // 1000:03d}+{v % 1000:03d}"
    except (TypeError, ValueError):
        return str(v or "")


# ── Paquete de entrega (ZIP con la estructura 6.3.5) ─────────────────────────
def construir_paquete(codigo, tipo, archivos_por_categoria=None,
                      informe=None, ppm=None, kmz=None) -> tuple[bytes, list]:
    """Arma el ZIP del entregable. Devuelve (zip_bytes, resumen_carpetas).

    archivos_por_categoria: {clave: [(nombre, bytes), ...]}  (de la carga)
    informe / ppm: (nombre, bytes) del informe y PPM generados
    kmz: bytes del KMZ
    """
    catmap = _cat_por_clave(tipo)
    root = codigo or f"Entrega_{tipo}"
    resumen = {}
    buf = io.BytesIO()
    z = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)

    def _add(carpeta, nombre, contenido):
        z.writestr(f"{root}/{carpeta}/{nombre}", contenido)
        resumen[carpeta.split('/')[0]] = resumen.get(carpeta.split('/')[0], 0) + 1

    if informe:
        _add(FOLDERS["anexos"], informe[0], informe[1])
    if kmz:
        _add(FOLDERS["anexos"], f"{codigo or 'inspeccion'}.kmz", kmz)
    if ppm:
        _add(FOLDERS["ppm"], ppm[0], ppm[1])

    for clave, files in (archivos_por_categoria or {}).items():
        c = catmap.get(clave)
        carpeta = FOLDERS.get(c["carpeta"], "99_Otros") if c else "99_Otros"
        if c and c.get("sub"):
            carpeta = f"{carpeta}/{c['sub']}"
        for i, (nombre, contenido) in enumerate(files, 1):
            # prefijo de orden para RF (contrato pide orden de abscisado)
            fn = f"{i:02d}_{nombre}" if (c and c["grupo"] == "rf") else nombre
            _add(carpeta, fn, contenido)

    # índice del paquete
    lineas = [f"PAQUETE DE ENTREGA — {codigo or tipo}", "",
              "Estructura (numeral 6.3.5 del contrato):"]
    for carp, n in sorted(resumen.items()):
        lineas.append(f"  {carp}/  — {n} archivo(s)")
    faltan = [k for k in ("06_RF",) if k not in resumen]
    if faltan:
        lineas += ["", "⚠️ Pendiente(s): " + ", ".join(faltan)]
    z.writestr(f"{root}/00_Indice.txt", "\n".join(lineas))
    z.close()
    return buf.getvalue(), sorted(resumen.items())
