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


def construir_kmz(nombre_doc, cp_puntos=None, defectos=None, hallazgos=None) -> bytes:
    """Construye un KMZ (KML comprimido) con la traza, los puntos coloreados por
    estado (CIPS/PAP), los defectos DCVG por severidad y los hallazgos."""
    estilos = "".join(
        f'<Style id="s_{k}"><IconStyle><color>{v}</color><scale>0.7</scale>'
        f'<Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>'
        f'</IconStyle></Style>' for k, v in _KML_COLOR.items())
    estilos += ('<Style id="s_linea"><LineStyle><color>ff8a8a8a</color>'
                '<width>2</width></LineStyle></Style>')

    cuerpo = []
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
        desc = (f"Abscisa: {_absc(d.get('abscisa'))}\nSeveridad %IR: "
                f"{d.get('severidad_pct')}\nClasificación: {clas}")
        car_def.append(_placemark(f"Defecto {_absc(d.get('abscisa'))}", d["lat"],
                                  d["lon"], f"s_{clas}", desc))
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
        car_h.append(_placemark(f"{h.get('tipo','Hallazgo')} {_absc(abv)}", la, lo,
                                "s_Hallazgo", desc))
    if car_h:
        cuerpo.append(f'<Folder><name>Hallazgos</name>{"".join(car_h)}</Folder>')

    kml = (f'<?xml version="1.0" encoding="UTF-8"?>'
           f'<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
           f'<name>{escape(nombre_doc)}</name>{estilos}{"".join(cuerpo)}'
           f'</Document></kml>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("doc.kml", kml)
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
