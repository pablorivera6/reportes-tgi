#!/usr/bin/env python3
"""Carga un informe histórico al portal, para la comparativa del dashboard.

Lee el informe de la inspección anterior (de PCC o de otro contratista), lo
convierte a un CSV liviano y lo publica en Supabase. El dashboard del portal y
su PDF descargable toman de ahí la comparación histórico vs. actual.

    python3 cargar_historico.py "CIPS_REP_R_DOR_11_23_..._TEL_Rev0.xlsx"
    python3 cargar_historico.py informe.xlsx --tramo "La Dorada" --periodo "Nov 2023"
    python3 cargar_historico.py informe.xlsx --solo-csv      # no toca Supabase
    python3 cargar_historico.py informe.xlsx --reemplazar    # pisa el que ya exista

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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("archivo", help="informe .xlsx de la inspección anterior")
    ap.add_argument("--tramo", help="nombre del tramo (si el informe no lo trae)")
    ap.add_argument("--periodo", help="p. ej. 'Nov 2023'")
    ap.add_argument("--csv", help="ruta del CSV de salida")
    ap.add_argument("--solo-csv", action="store_true",
                    help="genera el CSV y no publica en Supabase")
    ap.add_argument("--reemplazar", action="store_true",
                    help="borra el histórico existente del mismo tramo/tipo/periodo")
    args = ap.parse_args()

    if not os.path.exists(args.archivo):
        sys.exit(f"No existe el archivo: {args.archivo}")

    print(f"Leyendo {os.path.basename(args.archivo)} …")
    hist = historicos.leer_historico(args.archivo)
    if args.tramo:
        hist["tramo"] = args.tramo
    if args.periodo:
        hist["periodo"] = args.periodo
    if not hist["tramo"]:
        sys.exit("El informe no trae el tramo. Indícalo con --tramo \"La Dorada\".")

    r = hist["resumen"]
    print(f"  tramo       : {hist['tramo']}  ({hist['tipo']})")
    print(f"  periodo     : {hist['periodo'] or '(sin fecha)'}")
    print(f"  contratista : {hist['contratista'] or '—'}")
    print(f"  puntos      : {r['n']}")
    if r["n"]:
        print(f"  protegidos  : {r['pct_prot']}%  (fuera de criterio: {r['fuera']})")
        print(f"  OFF         : prom {r['prom_off']} mV · min {r['min_off']} · "
              f"max {r['max_off']}")
    if not r["n"]:
        sys.exit("No se leyeron puntos con potencial OFF: revisa la hoja del informe.")

    os.makedirs(CARPETA_CSV, exist_ok=True)
    csv_out = args.csv or _nombre_csv(hist)
    historicos.a_csv(hist, csv_out)
    peso_x = os.path.getsize(args.archivo) / 1024
    peso_c = os.path.getsize(csv_out) / 1024
    print(f"  CSV         : {csv_out}  ({peso_c:.0f} KB, del .xlsx de {peso_x:.0f} KB)")

    if args.solo_csv:
        print("\n(--solo-csv: no se publicó en el portal)")
        return

    sec = _secretos()
    if not sec.get("supabase", {}).get("service_key"):
        sys.exit("\nFalta [supabase] service_key en .streamlit/secrets.toml "
                 "para publicar. Puedes generar solo el CSV con --solo-csv.")
    import db
    # db.py lee las credenciales de st.secrets; fuera de Streamlit se le pasa
    # un objeto equivalente con el contenido de secrets.toml.
    db.st = type("_Secrets", (), {"secrets": sec})()

    previos = [h for h in db.listar_historicos(hist["tramo"], hist["tipo"])
               if (h.get("periodo") or "") == hist["periodo"]]
    if previos and not args.reemplazar:
        print(f"\n⚠️  Ya hay {len(previos)} histórico(s) de {hist['tramo']} "
              f"({hist['periodo']}) en el portal. Usa --reemplazar para pisarlo.")
        return
    for h in previos:
        db.borrar_historico(h["id"])
        print(f"  – reemplazado el histórico previo ({h['id']})")

    hid = db.guardar_historico(
        hist["tramo"], hist["tipo"], hist["periodo"],
        [{"abscisa": p["abscisa"], "on": p["on"], "off": p["off"]}
         for p in hist["puntos"]],
        fuente=f"{hist['contratista']} · {hist['fuente']}".strip(" ·"),
        fecha=None)
    print(f"\n✅ Publicado en el portal (id {hid}). El dashboard de "
          f"{hist['tramo']} ya muestra la comparativa y el PDF.")


if __name__ == "__main__":
    main()
