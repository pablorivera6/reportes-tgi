# mod_unificar.py
import pandas as pd
import glob
import os

# Máximo de filas de una hoja de Excel (menos el encabezado).
MAX_FILAS_EXCEL = 1_048_575


def _sin_filas_vacias(df):
    """Quita las filas sin ningún dato. Un export puede traer una celda suelta
    al final de la hoja (p.ej. un espacio en la fila 1.048.576) y pandas la
    lee como un millón de filas vacías: al unir varios archivos la tabla
    superaba el máximo de Excel. Una fila con cualquier dato real se conserva."""
    if df.empty:
        return df
    vacia = df.isna()
    for col in df.columns[(df.dtypes == object).values]:
        vacia[col] = vacia[col] | df[col].astype(str).str.strip().eq("")
    return df[~vacia.all(axis=1)]


def ejecutar_unificar(carpeta):
    ruta = os.path.join(carpeta, "*.xlsx")
    archivos = glob.glob(ruta)

    hojas_dict = {}

    # FASE 1: Unificar archivos
    for archivo in archivos:
        xls = pd.ExcelFile(archivo)
        for hoja in xls.sheet_names:
            df = _sin_filas_vacias(pd.read_excel(archivo, sheet_name=hoja))
            hojas_dict.setdefault(hoja, []).append(df)

    survey = pd.concat(hojas_dict["Survey Data"], ignore_index=True)
    dcp = pd.concat(hojas_dict["DCP Data"], ignore_index=True)

    dcp = dcp.reset_index(drop=True)
    dcp_unico = dcp.drop_duplicates(subset="Data No", keep="first")

    merged = survey.merge(
        dcp_unico[["Data No", "Device ID", "Comments"]],
        on="Data No",
        how="left"
    )

    # Regla FEA
    mask_fea = merged["Device ID"].astype(str).str.startswith("FEA")
    merged.loc[mask_fea, "Device ID"] = ""

    # Regla DCP
    mask_dcp = merged["Device ID"].astype(str).str.startswith("DCP")
    merged.loc[mask_dcp, "Device ID"] = ""

    # Asegurar texto y evitar NaN
    merged["Device ID"] = merged["Device ID"].fillna("").astype(str)
    merged["Comments"] = merged["Comments"].fillna("").astype(str)

    # Concatenar en nueva columna
    merged["Comentarios"] = (
        merged["Device ID"].str.strip() + 
        " | " + 
        merged["Comments"].str.strip()
    ).str.strip(" |")

    # Limpiar columnas auxiliares
    merged = merged.drop(columns=["Device ID", "Comments"])


    salida = os.path.join(carpeta, "UNIFICADO_FINAL.xlsx")

    # Sin este control, pandas falla al guardar con un error que no dice nada
    # ("At least one sheet must be visible").
    for nombre, tabla in (("Survey Data", merged), ("DCP Data", dcp)):
        if len(tabla) > MAX_FILAS_EXCEL:
            raise ValueError(
                f"Los archivos suman {len(tabla):,} filas en '{nombre}', más de "
                f"las {MAX_FILAS_EXCEL:,} que admite Excel. Revisa que no haya "
                f"archivos repetidos o que no sean exportes CIPS del equipo.")

    with pd.ExcelWriter(salida, engine="openpyxl") as writer:
        merged.to_excel(writer, sheet_name="Survey Data", index=False)
        dcp.to_excel(writer, sheet_name="DCP Data", index=False)

    return salida   # 👈 importante
