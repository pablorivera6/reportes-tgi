#!/usr/bin/env python3
"""Carga rectificadores a Supabase (tabla `rectificadores`, esquema v7).

Uso:
    python3 cargar_rectificadores.py [ruta_al_json] [--tramo "La Dorada"] [--reset]

- `ruta_al_json`: el `rectifiers_processed.json` (salida de parse_tgi.py). Por
  defecto busca en la carpeta del proyecto o en Downloads/Codigo_Matriz_TGI.
- `--tramo`: asigna ese tramo a TODOS los rectificadores cargados (opcional; si
  no se pasa, quedan sin tramo y se asignan luego desde el portal — revisor).
- `--reset`: borra los rectificadores previos del mismo archivo antes de cargar
  (para re-ejecutar sin duplicar).

Requisitos:
- Antes de correrlo, ejecuta `portal/schema_v7.sql` en el SQL Editor de Supabase.
- Lee credenciales de `.streamlit/secrets.toml` → [supabase] url + service_key.
"""
import json
import os
import sys
import tomllib

import rectificadores as rx

_AQUI = os.path.dirname(os.path.abspath(__file__))
_CANDIDATOS = [
    os.path.join(_AQUI, "rectifiers_processed.json"),
    os.path.expanduser("~/Downloads/Codigo_Matriz_TGI/rectifiers_processed.json"),
    "/tmp/rects_test.json",
]


def _secrets():
    ruta = os.path.join(_AQUI, ".streamlit", "secrets.toml")
    if not os.path.exists(ruta):
        sys.exit(f"No encuentro {ruta}. Corre el script desde la carpeta del proyecto.")
    with open(ruta, "rb") as f:
        return tomllib.load(f).get("supabase", {})


def _cliente():
    s = _secrets()
    url, key = s.get("url"), s.get("service_key")
    if not url or not key:
        sys.exit("Faltan url/service_key en [supabase] de .streamlit/secrets.toml.")
    from supabase import create_client
    return create_client(url, key)


def main():
    args = sys.argv[1:]
    tramo = None
    reset = "--reset" in args
    args = [a for a in args if a != "--reset"]
    if "--tramo" in args:
        i = args.index("--tramo")
        tramo = args[i + 1]
        del args[i:i + 2]
    ruta = args[0] if args else next((c for c in _CANDIDATOS if os.path.exists(c)), None)
    if not ruta or not os.path.exists(ruta):
        sys.exit("No encuentro rectifiers_processed.json. Pásalo como argumento.")

    datos = json.load(open(ruta, encoding="utf-8"))
    rects = [r for r in datos if r.get("placa")]        # descarta filas vacías/UNKNOWN
    fuente = os.path.basename(ruta)
    cli = _cliente()

    if reset:
        cli.table("rectificadores").delete().eq("fuente", fuente).execute()
        print(f"Borrados rectificadores previos de '{fuente}'.")

    n = 0
    for r in rects:
        placa = r.get("placa") or {}
        est = rx.estado_rectificador(r)
        fila = {
            "tramo": tramo, "tag": placa.get("TAG") or placa.get("ESTRUCTURA"),
            "estructura": placa.get("ESTRUCTURA"), "distrito": r.get("plant"),
            "fabricante": placa.get("FABRICANTE"), "modelo": placa.get("MODELO"),
            "serial": placa.get("SERIAL"), "estado": est["cls"],
            "payload": r, "resumen": rx.resumen_rectificador(r), "fuente": fuente,
        }
        cli.table("rectificadores").insert(fila).execute()
        n += 1
        print(f"  ✓ {fila['tag']} ({fila['distrito']}) — {est['txt']}")

    print(f"\nListo: {n} rectificadores cargados"
          + (f" al tramo '{tramo}'." if tramo else " (sin tramo; asígnalos en el portal)."))


if __name__ == "__main__":
    main()
