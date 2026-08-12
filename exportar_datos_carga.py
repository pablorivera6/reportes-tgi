#!/usr/bin/env python3
"""Exporta los tramos y el catálogo de casillas a `web_carga/data.js`.

La web estática de carga necesita las MISMAS listas que la app Streamlit
(`intake_app.py`): los tramos (de `cips_infra.InfraTramos`) y las casillas por
tipo de inspección (`entrega.CATALOGO`). Este script las vuelca a un JS que la
web incluye. Reejecutar cuando cambien la infraestructura o el catálogo.

Uso:  python3 exportar_datos_carga.py
"""
import json
import os

from entrega import CATALOGO

_AQUI = os.path.dirname(os.path.abspath(__file__))
_SALIDA = os.path.join(_AQUI, "web_carga", "data.js")


def _tramos():
    try:
        from cips_infra import InfraTramos
        infra = InfraTramos()
        nombres = set()
        for emp in infra.empresas():
            try:
                for t in infra.tramos(emp):
                    if t:
                        nombres.add(str(t))
            except Exception:
                continue
        return sorted(nombres)
    except Exception as e:
        print(f"  ⚠️ No se pudieron leer los tramos: {e}")
        return []


def main():
    tramos = _tramos()
    # CATALOGO tal cual (clave, etiqueta, req, tipos, grupo, sub) — la web no
    # necesita 'carpeta'; se queda igual por si sirve.
    catalogo = {tipo: [{"clave": c["clave"], "etiqueta": c["etiqueta"],
                        "req": c["req"], "tipos": c["tipos"], "grupo": c["grupo"]}
                       for c in casillas]
                for tipo, casillas in CATALOGO.items()}

    os.makedirs(os.path.dirname(_SALIDA), exist_ok=True)
    with open(_SALIDA, "w", encoding="utf-8") as f:
        f.write("// Generado por exportar_datos_carga.py — NO editar a mano.\n")
        f.write("window.TRAMOS = " + json.dumps(tramos, ensure_ascii=False) + ";\n")
        f.write("window.CATALOGO = " + json.dumps(catalogo, ensure_ascii=False,
                                                  indent=0) + ";\n")
    print(f"✓ {len(tramos)} tramos y {len(catalogo)} tipos → {_SALIDA}")


if __name__ == "__main__":
    main()
