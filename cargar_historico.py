#!/usr/bin/env python3
"""Carga un informe histórico al portal, para la comparativa del dashboard.

Lee el informe de la inspección anterior (de PCC o de otro contratista), lo
convierte a un CSV liviano y lo publica en Supabase. El dashboard del portal y
su PDF descargable toman de ahí la comparación histórico vs. actual.

    python3 cargar_historico.py "CIPS_REP_R_DOR_11_23_..._TEL_Rev0.xlsx"
    python3 cargar_historico.py informe.xlsx --tramo "La Dorada" --periodo "Nov 2023"
    python3 cargar_historico.py informe.xlsx --solo-csv      # no toca Supabase
    python3 cargar_historico.py informe.xlsx --reemplazar    # pisa el que ya exista
    python3 cargar_historico.py "Historicos inspecciones/"    # toda una carpeta

Sirve para CIPS/PAP (perfil de potenciales) y para DCVG (defectos de
recubrimiento con su severidad %IR); el tipo se deduce del informe.

Los .xlsx pesan ~2 MB; el CSV que genera, unas decenas de KB. Los CSV quedan en
`historicos/` (copia local auditable) y NO se suben al repo, que es público.
"""
import argparse
import os
import sys

import historicos

CARPETA_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historicos")


def _secretos():
    """Carga .streamlit/secrets.toml sin depender del runtime de Streamlit."""
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        ".streamlit", "secrets.toml")
    if not os.path.exists(ruta):
        return {}
    try:
        import tomllib
        with open(ruta, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"  ⚠️  no se pudo leer secrets.toml: {e}")
        return {}


def _nombre_csv(hist):
    partes = [hist.get("tipo", "CIPS"), hist.get("tramo", "tramo"),
              hist.get("periodo", "")]
    base = "_".join(p for p in partes if p)
    base = "".join(c if c.isalnum() or c in "._- " else "" for c in base)
    return os.path.join(CARPETA_CSV, base.replace(" ", "_") + ".csv")


def _archivos(entradas):
    """Expande carpetas y descarta temporales de Excel (~$…)."""
    rutas = []
    for e in entradas:
        if os.path.isdir(e):
            rutas += [os.path.join(e, n) for n in sorted(os.listdir(e))
                      if n.lower().endswith(".xlsx") and not n.startswith("~$")]
        else:
            rutas.append(e)
    return rutas


def _imprimir(hist):
    r = hist["resumen"]
    print(f"  tramo       : {hist['tramo']}  ({hist['tipo']})")
    print(f"  periodo     : {hist['periodo'] or '(sin fecha)'}")
    print(f"  contratista : {hist['contratista'] or '—'}")
    if hist["tipo"] == "DCVG":
        c = r["por_clasificacion"]
        print(f"  defectos    : {r['n_defectos']}  (críticos: {r['n_criticos']})")
        print(f"  severidad   : " + " · ".join(f"{k} {v}" for k, v in c.items()))
        print(f"  postes      : {r['n_postes']} · longitud {r['long_m'] or 0:.0f} m"
              f" · densidad {r['densidad_km'] if r['densidad_km'] is not None else '—'} def/km")
    else:
        print(f"  puntos      : {r['n']}")
        if r["n"]:
            print(f"  protegidos  : {r['pct_prot']}%  (fuera de criterio: {r['fuera']})")
            print(f"  OFF         : prom {r['prom_off']} mV · min {r['min_off']} · "
                  f"max {r['max_off']}")


def _vacio(hist):
    """¿El informe no aportó nada comparable?"""
    r = hist["resumen"]
    if hist["tipo"] == "DCVG":
        return not (r["n_defectos"] or r["n_postes"])
    return not r["n"]


def _publicar(hist, reemplazar):
    """Sube el histórico a Supabase. Devuelve el id, o None si ya existía."""
    import db
    previos = [h for h in db.listar_historicos(hist["tramo"], hist["tipo"])
               if (h.get("periodo") or "") == hist["periodo"]]
    if previos and not reemplazar:
        print(f"  ⚠️  ya está en el portal ({hist['periodo']}). "
              f"Usa --reemplazar para pisarlo.")
        return None
    for h in previos:
        db.borrar_historico(h["id"])
        print(f"  – reemplazado el histórico previo ({h['id']})")
    return db.guardar_historico(
        hist["tramo"], hist["tipo"], hist["periodo"], hist["puntos"],
        fuente=f"{hist['contratista']} · {hist['fuente']}".strip(" ·"),
        fecha=None, resumen=hist["resumen"])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivo", nargs="+",
                    help="informe(s) .xlsx de inspecciones anteriores, o una carpeta")
    ap.add_argument("--tramo", help="nombre del tramo (si el informe no lo trae)")
    ap.add_argument("--periodo", help="p. ej. 'Nov 2023'")
    ap.add_argument("--csv", help="ruta del CSV de salida (solo con un archivo)")
    ap.add_argument("--solo-csv", action="store_true",
                    help="genera el CSV y no publica en Supabase")
    ap.add_argument("--reemplazar", action="store_true",
                    help="borra el histórico existente del mismo tramo/tipo/periodo")
    args = ap.parse_args()

    rutas = _archivos(args.archivo)
    faltan = [r for r in rutas if not os.path.exists(r)]
    if faltan:
        sys.exit("No existe(n): " + ", ".join(faltan))
    if not rutas:
        sys.exit("No se encontró ningún .xlsx.")
    if (args.tramo or args.csv) and len(rutas) > 1:
        sys.exit("--tramo y --csv solo aplican cuando se carga un archivo.")

    if not args.solo_csv:
        sec = _secretos()
        if not sec.get("supabase", {}).get("service_key"):
            sys.exit("Falta [supabase] service_key en .streamlit/secrets.toml "
                     "para publicar. Puedes generar solo el CSV con --solo-csv.")
        import db
        # db.py lee las credenciales de st.secrets; fuera de Streamlit se le pasa
        # un objeto equivalente con el contenido de secrets.toml.
        db.st = type("_Secrets", (), {"secrets": sec})()

    os.makedirs(CARPETA_CSV, exist_ok=True)
    ok, saltados = [], []
    for ruta in rutas:
        print(f"\nLeyendo {os.path.basename(ruta)} …")
        try:
            hist = historicos.leer_historico(ruta)
        except Exception as e:
            print(f"  ❌ {e}")
            saltados.append((os.path.basename(ruta), str(e)))
            continue
        if args.tramo:
            hist["tramo"] = args.tramo
        if args.periodo:
            hist["periodo"] = args.periodo
        if not hist["tramo"]:
            print("  ❌ el informe no trae el tramo (usa --tramo)")
            saltados.append((os.path.basename(ruta), "sin tramo"))
            continue
        _imprimir(hist)
        if _vacio(hist):
            print("  ❌ no se leyeron datos: revisa la hoja del informe.")
            saltados.append((os.path.basename(ruta), "sin datos"))
            continue

        csv_out = args.csv or _nombre_csv(hist)
        historicos.a_csv(hist, csv_out)
        print(f"  CSV         : {os.path.basename(csv_out)} "
              f"({os.path.getsize(csv_out) / 1024:.0f} KB, del .xlsx de "
              f"{os.path.getsize(ruta) / 1024:.0f} KB)")
        if args.solo_csv:
            continue
        hid = _publicar(hist, args.reemplazar)
        if hid:
            print(f"  ✅ publicado en el portal (id {hid})")
            ok.append(f"{hist['tramo']} ({hist['tipo']} {hist['periodo']})")

    print(f"\n── Resumen: {len(ok)} publicado(s), {len(saltados)} sin cargar ──")
    for t in ok:
        print(f"  ✅ {t}")
    for n, e in saltados:
        print(f"  ❌ {n}: {e}")
    if args.solo_csv:
        print("(--solo-csv: no se publicó nada en el portal)")


if __name__ == "__main__":
    main()
