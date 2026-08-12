"""Rectificadores — visor y diagnóstico para el portal TGI.

Motor portado de la app web `Codigo_Matriz_TGI/app_tgi.js` (misma lógica de
estado, utilización y análisis de mantenimiento), más:
  - `render_seccion` / `render_card`: visor nativo en Streamlit (estilo PCC).
  - `pdf_rectificador`: PDF descargable de UN rectificador (matriz TGI).
  - `paginas_pdf`: dibuja las páginas de rectificadores dentro de un PdfPages
    existente (para meterlas en el PDF del dashboard del tramo).

Cada `rect` es un dict: {plant, placa{TAG,ESTRUCTURA,...}, nominales{...},
op_data{data:[{fecha,vac,iac,vdc,idc,tap,vshunt,r_circ} | {fecha,_event}]}, obs}.
"""
from __future__ import annotations

import io
import re

# Colores PCC
ROJO = "#C7113A"
VERDE = "#1A7A4A"
AMBAR = "#F59E0B"
AZUL = "#1F6FEB"
GRIS = "#646A73"

_NEG = re.compile(r"fuera|apagad|daña|abierto|desenergiz", re.I)
_POS = re.compile(r"puesta en marcha|se deja operando|instalaci|mantenimiento y puesta", re.I)


def _f(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def _placa(rect):
    return rect.get("placa") or {}


def _nom(rect):
    return rect.get("nominales") or {}


def _datos(rect):
    return (rect.get("op_data") or {}).get("data") or []


def tag_de(rect):
    p = _placa(rect)
    return p.get("TAG") or p.get("ESTRUCTURA") or rect.get("sheet") or "Rectificador"


# ── Estado operativo (port de getStatus) ─────────────────────────────────────
def estado_rectificador(rect):
    data = _datos(rect)
    if not data:
        return {"cls": "warn", "txt": "Sin datos op.", "color": AMBAR}
    last_data, last_err = -1, -1
    for i, r in enumerate(data):
        ev = r.get("_event")
        if not ev:
            last_data = i
        else:
            t = ev.lower()
            if _NEG.search(t) and not _POS.search(t):
                last_err = i
    if last_err > last_data and last_err >= 0:
        return {"cls": "err", "txt": "Fuera de servicio", "color": ROJO}
    return {"cls": "ok", "txt": "Operando", "color": VERDE}


# ── Utilización (port de calcUtil) ───────────────────────────────────────────
def calc_util(rect):
    n = _nom(rect)
    vnom, inom = _f(n.get("V_SALIDA_DC")), _f(n.get("I_SALIDA_DC"))
    if vnom is None or inom is None:
        return None
    num = [r for r in _datos(rect) if not r.get("_event") and (r.get("vdc") or r.get("idc"))]
    if not num:
        return None
    last = num[-1]
    vdc, idc = _f(last.get("vdc")), _f(last.get("idc"))
    return {
        "vPct": round(vdc / vnom * 100) if vdc and vnom else None,
        "iPct": round(idc / inom * 100) if idc and inom else None,
        "vdc": vdc, "idc": idc,
    }


# ── Análisis de mantenimiento (port de analyzeMaintenance) ───────────────────
def analizar_mantenimiento(rect, st_est, util):
    n = _nom(rect)
    p = _placa(rect)
    data = _datos(rect)
    needs, mejoras, preventivo = [], [], []
    refrig = (p.get("REFRIGERACION") or "").lower()

    diodo_ev = fuera_ev = circ_abierto = 0
    for row in data:
        ev = row.get("_event")
        if not ev:
            continue
        t = ev.lower()
        if re.search(r"diodo|stack", t):
            diodo_ev += 1
        if not _POS.search(t) and re.search(r"fuera de servicio|apagad|desenergiz", t):
            fuera_ev += 1
        if re.search(r"circuito abierto|cable.*fuera|punto caliente", t):
            circ_abierto += 1

    if st_est["cls"] == "err":
        eventos = [r for r in data if r.get("_event")]
        last_txt = eventos[-1]["_event"].lower() if eventos else ""
        if re.search(r"diodo|stack", last_txt):
            needs.append(("🔴", "Reemplazo de stack de diodos",
                          "El equipo reporta diodos dañados. Se requiere reemplazo inmediato del "
                          "stack de diodos rectificadores. Verificar compatibilidad con modelo "
                          f"{p.get('MODELO','')}. Tras el reemplazo, realizar prueba de carga progresiva.",
                          ROJO))
            mejoras.append(("💡", "Instalar diodos de mayor capacidad",
                            "Considerar diodos con mayor margen de corriente (20% sobre nominal) "
                            "para reducir fallas recurrentes."))
        elif re.search(r"circuito abierto|cable", last_txt):
            needs.append(("🔴", "Reparación de circuito abierto",
                          "Se detectó circuito abierto en el sistema. Inspeccionar cables positivo "
                          "y negativo, bornas y conexiones a camas anódicas. Verificar continuidad "
                          "con megóhmetro.", ROJO))
            mejoras.append(("💡", "Mejorar protección de cables",
                            "Instalar protección mecánica adicional en cables expuestos y mejorar "
                            "conexiones con terminales tipo compresión."))
        else:
            needs.append(("🔴", "Diagnóstico y puesta en marcha",
                          "Equipo fuera de servicio. Realizar diagnóstico completo: verificar "
                          "alimentación AC, fusibles, breakers, diodos, transformador y conexiones. "
                          "PRIORIDAD ALTA.", ROJO))

    if diodo_ev > 0 and st_est["cls"] != "err":
        needs.append(("⚠️", f"Historial de fallas en diodos ({diodo_ev} evento(s))",
                      "Antecedentes de fallas en diodos. Programar inspección termográfica "
                      "trimestral de semiconductores y verificar ventilación/refrigeración.", AMBAR))
        mejoras.append(("💡", "Upgrade de semiconductores",
                        "Evaluar reemplazo preventivo del stack de diodos por uno de mayor "
                        "capacidad o tecnología SCR/tiristores."))

    if circ_abierto > 0 and st_est["cls"] != "err":
        needs.append(("⚠️", f"Historial de circuitos abiertos ({circ_abierto} evento(s))",
                      "Se han registrado eventos de circuito abierto. Inspeccionar empalmes, "
                      "bornas y conectores. Verificar aislamiento con prueba de megger.", AMBAR))

    if util:
        ip, vp = util.get("iPct"), util.get("vPct")
        if ip is not None and ip > 90:
            needs.append(("⚠️", f"Sobrecarga de corriente ({ip}% de {n.get('I_SALIDA_DC')}A nominal)",
                          f"Corriente de salida: {util.get('idc')}A vs nominal: {n.get('I_SALIDA_DC')}A. "
                          "Supera el 90% de capacidad. Riesgo de sobrecalentamiento y falla prematura "
                          "de diodos y transformador.", ROJO))
            mejoras.append(("📈", "Ampliar capacidad del rectificador",
                            "Considerar reemplazo por rectificador de mayor potencia o instalar un "
                            "segundo rectificador en paralelo."))
        elif ip is not None and ip > 75:
            needs.append(("⚠️", f"Alta utilización de corriente ({ip}% de {n.get('I_SALIDA_DC')}A)",
                          f"Corriente: {util.get('idc')}A ({ip}% de nominal). Operar >75% reduce vida "
                          "útil. Monitorear tendencia y verificar si la demanda de protección catódica "
                          "aumenta por degradación del recubrimiento.", AMBAR))
            mejoras.append(("📈", "Optimizar distribución de corriente",
                            "Verificar estado de ánodos y redistribuir salidas para balancear carga."))
        if ip is not None and 0 < ip < 15:
            needs.append(("🔍", f"Corriente muy baja ({util.get('idc')}A = {ip}% de {n.get('I_SALIDA_DC')}A)",
                          "Posibles causas: circuito parcialmente abierto, ánodos agotados, "
                          "recubrimiento en buen estado, o TAP mal configurado. Verificar integridad "
                          "del circuito de protección.", AZUL))
            mejoras.append(("📈", "Verificar sistema de ánodos",
                            "Medir resistencia del lecho anódico y comparar con valores históricos."))
        if vp is not None and vp > 85:
            needs.append(("⚠️", f"Alto voltaje de operación ({util.get('vdc')}V = {vp}% de {n.get('V_SALIDA_DC')}V)",
                          "Voltaje cercano al máximo nominal indica alta resistividad del circuito "
                          "(lecho anódico degradado o cables con alta resistencia).", AMBAR))
            mejoras.append(("📈", "Refuerzo de cama anódica",
                            "Alta resistencia puede indicar agotamiento de ánodos. Instalar ánodos "
                            "de refuerzo reduciría voltaje y potencia consumida."))

    if fuera_ev >= 2:
        needs.append(("📊", f"Patrón de fallas recurrentes ({fuera_ev} eventos)",
                      "El rectificador ha estado fuera de servicio múltiples veces. Se recomienda "
                      "análisis de causa raíz (RCA) para identificar el factor común.", AMBAR))
        mejoras.append(("💡", "Plan de reemplazo programado",
                        f"Con {fuera_ev} eventos de falla, considerar incluir en plan de reemplazo. "
                        "Evaluar equipos con tecnología switching (más eficientes)."))

    if "aceite" in refrig:
        preventivo.append(("🛢️", "Mantenimiento de aceite dieléctrico",
                           "Verificar nivel, color y estado del aceite (claro/amarillo). Si oscuro "
                           "o con partículas, reemplazar. Verificar empaques. Frecuencia: semestral."))
    elif "aire" in refrig:
        preventivo.append(("🌀", "Limpieza del sistema de ventilación",
                           "Limpiar filtros y rejillas. Verificar ventiladores. En ambientes con "
                           "polvo, frecuencia trimestral."))

    if n.get("SHUNT"):
        preventivo.append(("⚡", f"Verificación de resistencia shunt ({n.get('SHUNT')})",
                           "Medir resistencia del shunt con micro-ohmetro vs valor nominal. "
                           "Desviación >5% indica desgaste. Frecuencia: anual."))
    preventivo += [
        ("🔌", "Inspección de conexiones eléctricas",
         "Verificar torque de terminales, buscar corrosión y puntos calientes. Reapretar "
         "conexiones flojas. Frecuencia: semestral."),
        ("🛡️", "Prueba de protectores (Arresters/Varistores)",
         "Verificar integridad de arresters AC/DC y varistores. Reemplazar si dañados. Anual."),
        ("📏", "Calibración de instrumentos",
         "Verificar lecturas del panel contra multímetro calibrado. Desviación >5% requiere "
         "recalibración. Frecuencia: anual."),
        ("🔋", "Verificación de fusibles y breakers",
         "Inspeccionar fusibles AC/DC y breaker. Reemplazar deteriorados. Frecuencia: semestral."),
    ]

    # Tendencia de corriente
    num = [r for r in data if not r.get("_event") and _f(r.get("idc")) and _f(r.get("idc")) > 0]
    if len(num) >= 3:
        i0, i1 = _f(num[0].get("idc")), _f(num[-1].get("idc"))
        if i0 and i1 and i0 > 0:
            chg = round((i1 - i0) / i0 * 100)
            if abs(chg) > 30:
                tend = "aumentado" if chg > 0 else "disminuido"
                det = (f"Corriente: de {i0:.1f}A a {i1:.1f}A entre primera y última inspección. "
                       + ("Aumento sostenido puede indicar degradación del recubrimiento o "
                          "deterioro de ánodos." if chg > 0 else
                          "Disminución puede indicar circuitos abiertos, ánodos agotados o mejora "
                          "del recubrimiento. Verificar integridad del circuito."))
                mejoras.append(("📊", f"Tendencia de corriente: {tend} {abs(chg)}%", det))

    return {"needs": needs, "mejoras": mejoras, "preventivo": preventivo}


def resumen_rectificador(rect):
    """Dict compacto para guardar/listar (estado + utilización + conteos)."""
    est = estado_rectificador(rect)
    util = calc_util(rect)
    data = _datos(rect)
    return {"estado": est["cls"], "estado_txt": est["txt"],
            "util": util, "n_op": sum(1 for r in data if not r.get("_event")),
            "n_eventos": sum(1 for r in data if r.get("_event"))}


# ── Utilidades de tabla de operación ─────────────────────────────────────────
_OP_COLS = ["Fecha", "V Shunt (mV)", "TAP", "VAC", "IAC", "VDC", "IDC", "R Circ (Ω)"]


def _op_filas(rect):
    filas, eventos = [], []
    for row in _datos(rect):
        if row.get("_event"):
            eventos.append((row.get("fecha", ""), row["_event"]))
            continue
        filas.append([row.get("fecha", ""), row.get("vshunt", ""), row.get("tap", ""),
                      row.get("vac", ""), row.get("iac", ""), row.get("vdc", ""),
                      row.get("idc", ""), row.get("r_circ", "")])
    return filas, eventos


# ── Render en Streamlit (portal) ─────────────────────────────────────────────
def render_card(rect, st, key, permitir_pdf=True):
    p, n = _placa(rect), _nom(rect)
    est = estado_rectificador(rect)
    util = calc_util(rect)
    tag = tag_de(rect)

    with st.container(border=True):
        c1, c2 = st.columns([4, 1])
        with c1:
            st.markdown(f"**{tag}** &nbsp; <span style='color:#666'>{p.get('ESTRUCTURA','')}</span>",
                        unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div style='text-align:right'><span style='background:{est['color']}22;"
                        f"color:{est['color']};padding:.15rem .6rem;border-radius:999px;"
                        f"font-weight:700;font-size:.78rem'>{est['txt']}</span></div>",
                        unsafe_allow_html=True)

        ic = st.columns(4)
        for i, (k, v) in enumerate([("Fabricante", p.get("FABRICANTE")), ("Modelo", p.get("MODELO")),
                                    ("Serial", p.get("SERIAL")), ("Refrigeración", p.get("REFRIGERACION"))]):
            ic[i].markdown(f"<span style='color:#9AA0A6;font-size:.7rem'>{k.upper()}</span><br>"
                           f"<b>{v or '—'}</b>", unsafe_allow_html=True)

        nc = st.columns(4)
        for i, (k, v) in enumerate([("V salida DC", f"{n.get('V_SALIDA_DC','—')} V"),
                                    ("I salida DC", f"{n.get('I_SALIDA_DC','—')} A"),
                                    ("V entrada AC", f"{n.get('V_ENTRADA_AC','—')} V"),
                                    ("Shunt", n.get("SHUNT") or "—")]):
            nc[i].markdown(f"<span style='color:#9AA0A6;font-size:.7rem'>{k.upper()}</span><br>"
                           f"<b>{v}</b>", unsafe_allow_html=True)

        if util:
            uc = st.columns(2)
            if util.get("vPct") is not None:
                uc[0].caption(f"Utilización V: {util['vPct']}%")
                uc[0].progress(min(util["vPct"], 100) / 100)
            if util.get("iPct") is not None:
                uc[1].caption(f"Utilización I: {util['iPct']}%")
                uc[1].progress(min(util["iPct"], 100) / 100)

        with st.expander("Ver detalles y diagnóstico"):
            filas, eventos = _op_filas(rect)
            if filas:
                import pandas as pd
                st.markdown(f"**Datos operacionales** ({len(filas)} registros"
                            + (f", {len(eventos)} eventos" if eventos else "") + ")")
                st.dataframe(pd.DataFrame(filas, columns=_OP_COLS),
                             use_container_width=True, hide_index=True, height=min(60 + 35 * len(filas), 260))
            if eventos:
                for fecha, ev in eventos:
                    st.caption(f"📌 {fecha} · {ev[:200]}")

            diag = analizar_mantenimiento(rect, est, util)
            if diag["needs"]:
                st.markdown(f"<b style='color:{AMBAR}'>🔧 Necesidades de mantenimiento</b>",
                            unsafe_allow_html=True)
                for m in diag["needs"]:
                    st.markdown(f"- {m[0]} **{m[1]}** — {m[2]}")
            if diag["mejoras"]:
                st.markdown(f"<b style='color:{VERDE}'>📈 Mejoras recomendadas</b>",
                            unsafe_allow_html=True)
                for m in diag["mejoras"]:
                    st.markdown(f"- {m[0]} **{m[1]}** — {m[2]}")
            if diag["preventivo"]:
                st.markdown(f"<b style='color:{AZUL}'>🛡️ Mantenimiento preventivo</b>",
                            unsafe_allow_html=True)
                for m in diag["preventivo"]:
                    st.markdown(f"- {m[0]} **{m[1]}** — {m[2]}")

            if permitir_pdf:
                try:
                    st.download_button("⬇️ PDF de este rectificador", data=pdf_rectificador(rect),
                                       file_name=f"Rectificador_{tag.replace(' ', '_')}.pdf",
                                       mime="application/pdf", key=f"pdfrect_{key}")
                except Exception as e:
                    st.caption(f"(No se pudo generar el PDF: {e})")


def kpis(rects):
    total = len(rects)
    distritos = len({r.get("plant") or _placa(r).get("DISTRITO") or "—" for r in rects})
    op = sum(1 for r in rects if estado_rectificador(r)["cls"] == "ok")
    err = sum(1 for r in rects if estado_rectificador(r)["cls"] == "err")
    return {"total": total, "distritos": distritos, "operando": op, "fuera": err}


# ── PDF ──────────────────────────────────────────────────────────────────────
def _cabecera(fig, plt, titulo, sub, pag, total_pag):
    fig.text(0.06, 0.955, titulo, fontsize=15, fontweight="bold", color="#191C20")
    fig.text(0.06, 0.930, sub, fontsize=9.5, color=GRIS)
    fig.text(0.94, 0.955, "PCC Integrity", fontsize=12, fontweight="bold", color=ROJO, ha="right")
    fig.text(0.94, 0.932, f"Portal TGI · pág. {pag}/{total_pag}", fontsize=8, color=GRIS, ha="right")
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.918, 0.918], color=ROJO, lw=2,
                              transform=fig.transFigure))


def _tabla(fig, plt, rect_box, titulo, colnames, filas, anchos=None, fs=7.5):
    ax = fig.add_axes(rect_box); ax.axis("off")
    if titulo:
        ax.text(0, 1.02, titulo, transform=ax.transAxes, fontsize=10, fontweight="bold",
                color="#191C20", va="bottom")
    if not filas:
        ax.text(0, 0.9, "Sin registros.", transform=ax.transAxes, fontsize=8.5,
                color="#9AA0A6", va="top")
        return
    t = ax.table(cellText=filas, colLabels=colnames, cellLoc="center",
                 colWidths=anchos, loc="upper center")
    t.auto_set_font_size(False); t.set_fontsize(fs); t.scale(1, 1.28)
    for (r, c), cell in t.get_celld().items():
        cell.set_edgecolor("#E3E5E9"); cell.set_linewidth(0.6)
        if r == 0:
            cell.set_facecolor(ROJO); cell.set_text_props(color="white", fontweight="bold")
        elif r % 2 == 0:
            cell.set_facecolor("#FAFAFA")


def _corta(texto, n):
    """Recorta en el último espacio antes de `n` para no partir palabras."""
    t = str(texto or "").strip()
    if len(t) <= n:
        return t
    corte = t[:n].rsplit(" ", 1)[0]
    return (corte or t[:n]) + "…"


def _fila_resumen(rect):
    p, n = _placa(rect), _nom(rect)
    est = estado_rectificador(rect)
    util = calc_util(rect) or {}
    ipct = f"{util['iPct']}%" if util.get("iPct") is not None else "—"
    return [tag_de(rect)[:18], (p.get("ESTRUCTURA") or "")[:16], est["txt"],
            f"{n.get('V_SALIDA_DC','—')}/{n.get('I_SALIDA_DC','—')}",
            f"{util.get('vdc','—')}/{util.get('idc','—')}", ipct]


def paginas_pdf(pdf, plt, rects, titulo, pag_ini, total_pag):
    """Dibuja las páginas de rectificadores dentro de un PdfPages abierto.

    Devuelve el número de la siguiente página. Página 1: resumen + tabla; luego
    una página de diagnóstico con las necesidades de mantenimiento del tramo.
    """
    k = kpis(rects)
    fig = plt.figure(figsize=(8.3, 11.7), dpi=150)
    _cabecera(fig, plt, titulo, "Rectificadores del tramo — estado de operación", pag_ini, total_pag)
    for i, (lbl, val, col) in enumerate([
            ("Rectificadores", k["total"], ROJO), ("Distritos", k["distritos"], "#191C20"),
            ("En operación", k["operando"], VERDE), ("Fuera de servicio", k["fuera"], ROJO)]):
        x = 0.06 + i * 0.235
        fig.text(x, 0.875, str(val), fontsize=20, fontweight="bold", color=col)
        fig.text(x, 0.850, lbl, fontsize=8, color=GRIS)
    filas = [_fila_resumen(r) for r in rects]
    _tabla(fig, plt, [0.06, 0.09, 0.88, 0.72], "Inventario de rectificadores",
           ["TAG", "Estructura", "Estado", "V/I nom", "V/I últ.", "%I"], filas,
           anchos=[0.20, 0.20, 0.20, 0.15, 0.15, 0.10], fs=7)
    pdf.savefig(fig); plt.close(fig)
    pag = pag_ini + 1

    # Página de necesidades de mantenimiento (solo lo relevante)
    crit = []
    for r in rects:
        est = estado_rectificador(r)
        diag = analizar_mantenimiento(r, est, calc_util(r))
        for m in diag["needs"]:
            crit.append([tag_de(r)[:16], _corta(m[1], 32), _corta(m[2], 62)])
    if crit:
        fig = plt.figure(figsize=(8.3, 11.7), dpi=150)
        _cabecera(fig, plt, titulo, "Necesidades de mantenimiento detectadas", pag, total_pag)
        _tabla(fig, plt, [0.06, 0.08, 0.88, 0.76], f"Acciones recomendadas ({len(crit)})",
               ["Rectificador", "Necesidad", "Detalle"], crit,
               anchos=[0.18, 0.30, 0.52], fs=6.8)
        pdf.savefig(fig); plt.close(fig)
        pag += 1
    return pag


def paginas_pdf_count(rects):
    """Cuántas páginas añade `paginas_pdf` (para el numerado del PDF)."""
    if not rects:
        return 0
    hay_crit = any(analizar_mantenimiento(r, estado_rectificador(r), calc_util(r))["needs"]
                   for r in rects)
    return 2 if hay_crit else 1


def pdf_rectificador(rect) -> bytes:
    """PDF de UN rectificador (matriz TGI): placa, nominales, operación y diagnóstico."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    p, n = _placa(rect), _nom(rect)
    est = estado_rectificador(rect)
    util = calc_util(rect)
    tag = tag_de(rect)
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        fig = plt.figure(figsize=(8.3, 11.7), dpi=150)
        _cabecera(fig, plt, tag, f"Rectificador · {p.get('ESTRUCTURA','')} · {rect.get('plant','')}", 1, 1)
        fig.text(0.94, 0.905, est["txt"], fontsize=11, fontweight="bold", color=est["color"], ha="right")

        # Placa
        placa = [("Fabricante", p.get("FABRICANTE")), ("Modelo", p.get("MODELO")),
                 ("Serial", p.get("SERIAL")), ("Temperatura", p.get("TEMPERATURA")),
                 ("Refrigeración", p.get("REFRIGERACION")), ("Distrito", rect.get("plant"))]
        y = 0.88
        fig.text(0.06, y + 0.015, "DATOS DE PLACA", fontsize=9, fontweight="bold", color="#191C20")
        for i, (k, v) in enumerate(placa):
            x = 0.06 + (i % 3) * 0.30
            if i % 3 == 0 and i:
                y -= 0.04
            fig.text(x, y, k.upper(), fontsize=6.8, color="#9AA0A6")
            fig.text(x, y - 0.016, str(v or "—"), fontsize=9, color="#191C20", fontweight="bold")

        # Nominales
        y2 = y - 0.06
        fig.text(0.06, y2 + 0.015, "DATOS NOMINALES", fontsize=9, fontweight="bold", color="#191C20")
        nomi = [("V salida DC", f"{n.get('V_SALIDA_DC','—')} V"), ("I salida DC", f"{n.get('I_SALIDA_DC','—')} A"),
                ("V entrada AC", f"{n.get('V_ENTRADA_AC','—')} V"), ("I entrada AC", f"{n.get('I_ENTRADA_AC','—')} A"),
                ("Shunt", n.get("SHUNT") or "—"), ("Utilización I", f"{util['iPct']}%" if util and util.get("iPct") is not None else "—")]
        yy = y2
        for i, (k, v) in enumerate(nomi):
            x = 0.06 + (i % 3) * 0.30
            if i % 3 == 0 and i:
                yy -= 0.04
            fig.text(x, yy, k.upper(), fontsize=6.8, color="#9AA0A6")
            fig.text(x, yy - 0.016, str(v), fontsize=9, color="#191C20", fontweight="bold")

        # Operación
        filas, eventos = _op_filas(rect)
        filas_fmt = [[str(c)[:10] for c in f] for f in filas[:18]]
        _tabla(fig, plt, [0.06, 0.30, 0.88, min(0.02 + 0.03 * max(len(filas_fmt), 1), 0.30)],
               f"Datos de operación ({len(filas)} registros)", _OP_COLS, filas_fmt,
               anchos=[0.16, 0.14, 0.10, 0.11, 0.11, 0.11, 0.11, 0.16], fs=6.5)

        # Diagnóstico (necesidades + mejoras, texto)
        diag = analizar_mantenimiento(rect, est, util)
        ty = 0.27
        fig.text(0.06, ty, "DIAGNÓSTICO Y MANTENIMIENTO", fontsize=9, fontweight="bold", color="#191C20")
        ty -= 0.02
        líneas = [("Mant. " + m[1], AMBAR) for m in diag["needs"]] + \
                 [("Mejora: " + m[1], VERDE) for m in diag["mejoras"][:4]]
        if not líneas:
            líneas = [("Sin necesidades críticas detectadas. Aplicar plan preventivo estándar.", VERDE)]
        for txt, col in líneas[:9]:
            fig.text(0.07, ty, "• " + txt[:95], fontsize=7.6, color=col)
            ty -= 0.019
        pdf.savefig(fig); plt.close(fig)
    return buf.getvalue()
