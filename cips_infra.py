"""Resolución Empresa/Distrito/Tramo -> shapefile, vía el Excel de infraestructura.

Réplica de la lógica del sidebar de proceso-cips: OCENSA usa tramo directo;
TGI usa Distrito -> Tramo. El Excel tiene columnas: ID TRAMO, TRAMO, DISTRITO.
"""
import os
import sys
import zipfile
import tempfile
import pandas as pd

# Extensiones que necesita pyshp para leer una traza (el .gpkg no se usa).
_SHP_EXTS = (".shp", ".shx", ".dbf", ".prj", ".cpg")


def _resource_path(rel):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


class InfraTramos:
    def __init__(self, excel_path=None, shapefiles_dir=None, shapefiles_zip=None):
        self.excel_path = excel_path or _resource_path(
            "Listado de Infraestructura para Cod Informes.xlsx")
        self.shapefiles_dir = shapefiles_dir or _resource_path("shapefiles")
        # En la app empaquetada los shapefiles viajan comprimidos en un solo
        # .zip (un archivo se empaqueta mucho más rápido que 1547 sueltos).
        self.shapefiles_zip = shapefiles_zip or _resource_path("shapefiles.zip")
        self._cache_dir = None
        self.df = pd.read_excel(self.excel_path)

    def empresas(self):
        return ["TGI", "OCENSA"]

    def distritos_tgi(self):
        sub = self.df[self.df["DISTRITO"] != "OCENSA"]
        return sorted(sub["DISTRITO"].dropna().unique().tolist())

    def tramos(self, empresa, distrito=None):
        if empresa == "OCENSA":
            sub = self.df[self.df["DISTRITO"] == "OCENSA"]
        else:
            sub = self.df[self.df["DISTRITO"] != "OCENSA"]
            if distrito:
                sub = sub[sub["DISTRITO"] == distrito]
        return sub["TRAMO"].dropna().astype(str).tolist()

    def shapefile(self, empresa, tramo, distrito=None):
        if empresa == "OCENSA":
            fila = self.df[(self.df["DISTRITO"] == "OCENSA") &
                           (self.df["TRAMO"] == tramo)]
        else:
            cond = (self.df["DISTRITO"] != "OCENSA") & (self.df["TRAMO"] == tramo)
            if distrito:
                cond = (self.df["DISTRITO"] == distrito) & (self.df["TRAMO"] == tramo)
            fila = self.df[cond]
        if fila.empty:
            return None
        id_tramo = str(fila["ID TRAMO"].values[0])

        # 1. Carpeta suelta (desarrollo / código fuente).
        ruta = os.path.join(self.shapefiles_dir, id_tramo + ".shp")
        if os.path.exists(ruta):
            return ruta

        # 2. Desde shapefiles.zip (app empaquetada): extrae solo este tramo.
        if os.path.exists(self.shapefiles_zip):
            return self._extraer_de_zip(id_tramo)

        return None

    def sugerir_tramos(self, lat, lon, margen=0.05, max_seg=10.0):
        """Tramos cuyo bounding box (±margen grados) contiene el punto dado.

        Lee SOLO el header de cada .shp (bytes 36-68 = bbox), así que es
        barato; aún así se corta a max_seg segundos por si el filesystem es
        lento (iCloud). Devuelve [(TRAMO, DISTRITO, ID TRAMO), ...].
        """
        import struct
        import time

        def _bbox_archivo(ruta):
            with open(ruta, "rb") as f:
                head = f.read(68)
            return struct.unpack("<4d", head[36:68])

        def _bbox_zip(z, nombre):
            with z.open(nombre) as f:
                head = f.read(68)
            return struct.unpack("<4d", head[36:68])

        inicio = time.time()
        sugerencias = []
        usa_dir = os.path.isdir(self.shapefiles_dir)
        z = None
        if not usa_dir and os.path.exists(self.shapefiles_zip):
            z = zipfile.ZipFile(self.shapefiles_zip)
        try:
            for _, fila in self.df.dropna(subset=["ID TRAMO"]).iterrows():
                if time.time() - inicio > max_seg:
                    break
                id_tramo = str(fila["ID TRAMO"])
                try:
                    if usa_dir:
                        ruta = os.path.join(self.shapefiles_dir, id_tramo + ".shp")
                        if not os.path.exists(ruta):
                            continue
                        minx, miny, maxx, maxy = _bbox_archivo(ruta)
                    elif z is not None:
                        minx, miny, maxx, maxy = _bbox_zip(z, id_tramo + ".shp")
                    else:
                        break
                except Exception:
                    continue
                if (minx - margen <= lon <= maxx + margen and
                        miny - margen <= lat <= maxy + margen):
                    sugerencias.append((str(fila["TRAMO"]),
                                        str(fila["DISTRITO"]), id_tramo))
        finally:
            if z is not None:
                z.close()
        return sugerencias

    def _extraer_de_zip(self, id_tramo):
        """Extrae los archivos de un tramo del .zip a una carpeta caché y
        devuelve la ruta del .shp (o None si el tramo no está en el zip)."""
        if self._cache_dir is None:
            self._cache_dir = os.path.join(tempfile.gettempdir(), "tgi_shapefiles")
            os.makedirs(self._cache_dir, exist_ok=True)

        shp_out = os.path.join(self._cache_dir, id_tramo + ".shp")
        if os.path.exists(shp_out):
            return shp_out

        with zipfile.ZipFile(self.shapefiles_zip) as z:
            nombres = set(z.namelist())
            for ext in _SHP_EXTS:
                nombre = id_tramo + ext
                if nombre in nombres:
                    z.extract(nombre, self._cache_dir)

        return shp_out if os.path.exists(shp_out) else None
