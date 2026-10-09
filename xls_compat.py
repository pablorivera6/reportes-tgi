"""Compatibilidad con .xls (Excel 97-2003).

El logger de campo exporta la data cruda en .xls ('28-09-26 RAMAL TAUSA ...
2+420.xls'), pero el motor lee con openpyxl, que solo entiende .xlsx. En vez de
tocar cada lector, el archivo se convierte a .xlsx al subirlo: mismas hojas,
mismas celdas, y el resto del flujo no cambia.
"""
import os

import pandas as pd


def a_xlsx(ruta):
    """Si `ruta` es .xls, escribe al lado una copia .xlsx con todas sus hojas
    (celda por celda, sin inventar encabezados) y devuelve la nueva ruta. Con
    cualquier otra extensión devuelve la ruta tal cual."""
    base, ext = os.path.splitext(ruta)
    if ext.lower() != ".xls":
        return ruta
    try:
        hojas = pd.read_excel(ruta, sheet_name=None, header=None, engine="xlrd")
    except Exception as e:
        raise ValueError(
            f"No se pudo leer '{os.path.basename(ruta)}' como Excel 97-2003 "
            f"({e}). Ábrelo en Excel, guárdalo como .xlsx y súbelo de nuevo."
        ) from e
    destino = base + ".xlsx"
    with pd.ExcelWriter(destino, engine="openpyxl") as w:
        for nombre, df in hojas.items():
            df.to_excel(w, sheet_name=nombre, header=False, index=False)
    return destino
