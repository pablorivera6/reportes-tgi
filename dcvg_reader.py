"""Lectura de los archivos FastField de DCVG y Resistividades.

El export de FastField trae una hoja `Root` con la metadata y subformularios
(`subform_N`) con las filas repetibles. Para DCVG:
  - subform_5 = postes (potenciales de estructura)
  - subform_9 = defectos de recubrimiento
Para Resistividades:
  - subform_7 = medidas Wenner (1/2/3 m)

Las funciones son tolerantes: nombres de columna con espacios/tildes variables,
celdas vacías, y coordenadas "lat,lon" en un solo campo.
"""
import re

import openpyxl

# Etiqueta de abscisa que escribe el técnico: "5+760", "136+300", "PK 2+000".
_RE_PK = re.compile(r'(\d+)\s*\+\s*(\d+)')


def parse_pk(texto):
    """'5+760' -> 5760 (metros). None si no hay patрón K+M."""
    if texto is None:
        return None
    m = _RE_PK.search(str(texto))
    if not m:
        return None
    return int(m.group(1)) * 1000 + int(m.group(2))


def parse_coords(texto):
    """'4.5290577,-75.7461' -> (4.5290577, -75.7461). (None, None) si no aplica."""
    if texto is None:
        return (None, None)
    partes = str(texto).replace(";", ",").split(",")
    if len(partes) < 2:
        return (None, None)
    try:
        return (float(partes[0].strip()), float(partes[1].strip()))
    except (ValueError, TypeError):
        return (None, None)


def caracter_corto(txt):
    """'Catódico-Catódico' -> 'CC'; 'Catódico-Anódico' -> 'CA'; etc."""
    if not txt:
        return ""
    t = str(txt).lower()
    partes = re.split(r'[-/]', t)
    if len(partes) >= 2:
        a = "C" if "cat" in partes[0] else ("A" if "an" in partes[0] else "")
        b = "C" if "cat" in partes[1] else ("A" if "an" in partes[1] else "")
        if a and b:
            return a + b
    return ""


def clasificar_severidad(pct_ir):
    """Clasificación de severidad DCVG por %IR (umbrales PCC/TGI)."""
    if pct_ir is None:
        return ""
    v = abs(float(pct_ir))
    if v <= 15:
        return "Muy Pequeño"
    if v <= 35:
        return "Pequeño"
    if v <= 60:
        return "Mediano"
    return "Grande"


# ── Helpers de hoja/columna ───────────────────────────────────────────────────

def _norm(s):
    return re.sub(r'\s+', ' ', str(s or "").strip().lower())


def _indice_columnas(fila_encabezados):
    """Mapa nombre_normalizado -> índice de columna (0-based)."""
    return {_norm(v): i for i, v in enumerate(fila_encabezados) if v is not None}


def _col(idx_map, *nombres):
    """Devuelve el índice de la primera columna cuyo nombre normalizado empiece
    por alguno de los dados; None si no está."""
    for n in nombres:
        nn = _norm(n)
        for nombre, i in idx_map.items():
            if nombre == nn or nombre.startswith(nn):
                return i
    return None


def _num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def _filas(ws):
    return [r for r in ws.iter_rows(values_only=True) if r and any(c is not None for c in r)]


# ── Lectores ──────────────────────────────────────────────────────────────────

def leer_dcvg_fastfield(ruta):
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    meta = {"contratista": "", "fecha": "", "cliente": "", "tramo": "", "tecnico": ""}
    if "Root" in wb.sheetnames:
        rf = _filas(wb["Root"])
        if len(rf) >= 2:
            im = _indice_columnas(rf[0])
            fila = rf[1]

            def g(*n):
                i = _col(im, *n)
                return str(fila[i]).strip() if i is not None and fila[i] is not None else ""
            meta.update(contratista=g("Contratista"), fecha=g("Fecha"),
                        cliente=g("Cliente"), tramo=g("Troncal o ramal"),
                        tecnico=g("Técnico a cargo", "Tecnico a cargo"))

    postes = []
    if "subform_5" in wb.sheetnames:
        rf = _filas(wb["subform_5"])
        if len(rf) >= 2:
            im = _indice_columnas(rf[0])
            ci = {k: _col(im, *v) for k, v in {
                "tipo": ("Tipo de poste",), "pk": ("PK",), "on": ("ON",),
                "off": ("OFF",), "vac": ("Voltaje AC",), "res": ("Resistencia",),
                "coord": ("Coordenadas",)}.items()}
            for fila in rf[1:]:
                def v(k):
                    i = ci[k]
                    return fila[i] if i is not None and i < len(fila) else None
                lat, lon = parse_coords(v("coord"))
                postes.append({
                    "tipo": str(v("tipo") or "").strip(), "pk_m": parse_pk(v("pk")),
                    "on": _num(v("on")), "off": _num(v("off")), "vac": _num(v("vac")),
                    "resistencia": _num(v("res")), "lat": lat, "lon": lon})

    defectos = []
    if "subform_9" in wb.sheetnames:
        rf = _filas(wb["subform_9"])
        if len(rf) >= 2:
            im = _indice_columnas(rf[0])
            ci = {k: _col(im, *v) for k, v in {
                "sector": ("Sector",), "ubic": ("Ubicación", "Ubicacion"),
                "pk": ("PK del defecto",), "fn": ("Forma N",), "fs": ("Forma S",),
                "fe": ("Forma E",), "fo": ("Forma O",), "olre": ("OL/RE",),
                "prof": ("Profundidad",), "clas": ("Clasificación", "Clasificacion"),
                "reloj": ("Forma del defecto",), "com": ("Comentarios",),
                "car": ("Caracter de la indicación", "Caracter")}.items()}
            for fila in rf[1:]:
                def v(k):
                    i = ci[k]
                    return fila[i] if i is not None and i < len(fila) else None
                lat, lon = parse_coords(v("ubic"))
                defectos.append({
                    "sector": str(v("sector") or "").strip(), "lat": lat, "lon": lon,
                    "pk_m": parse_pk(v("pk")),
                    "forma_n": _num(v("fn")), "forma_s": _num(v("fs")),
                    "forma_e": _num(v("fe")), "forma_o": _num(v("fo")),
                    "ol_re": _num(v("olre")), "profundidad": _num(v("prof")),
                    "clasificacion_campo": str(v("clas") or "").strip(),
                    "posicion_reloj": str(v("reloj") or "").strip(),
                    "comentarios": str(v("com") or "").strip(),
                    "caracter": caracter_corto(v("car"))})
    wb.close()
    return {"meta": meta, "postes": postes, "defectos": defectos}


def leer_resistividades_fastfield(ruta):
    wb = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    out = []
    if "subform_7" in wb.sheetnames:
        rf = _filas(wb["subform_7"])
        if len(rf) >= 2:
            im = _indice_columnas(rf[0])
            ci = {k: _col(im, *v) for k, v in {
                "pk": ("PK",), "sector": ("Sector",), "prof": ("Profundidad",),
                "ubic": ("Ubicación", "Ubicacion"),
                "r1": ("Resistencia 1 metro",), "r2": ("Resistencia 2 metros",),
                "r3": ("Resistencia 3 metros",)}.items()}
            for fila in rf[1:]:
                def v(k):
                    i = ci[k]
                    return fila[i] if i is not None and i < len(fila) else None
                lat, lon = parse_coords(v("ubic"))
                out.append({
                    "pk_m": parse_pk(v("pk")), "sector": str(v("sector") or "").strip(),
                    "profundidad": _num(v("prof")), "lat": lat, "lon": lon,
                    "r1": _num(v("r1")), "r2": _num(v("r2")), "r3": _num(v("r3"))})
    wb.close()
    return out
