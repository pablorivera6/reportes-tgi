"""Comparativa CIPS: inspección actual vs histórico de un tramo.

- `overlay_plotly`: gráfica interactiva para el portal (perfil OFF vs abscisa).
- `resumen_comparativo`: métricas antes/ahora.
- `pdf_bytes`: PDF de una página (matplotlib, sirve en Streamlit Cloud sin Chrome).
"""
from __future__ import annotations

import io

ROJO = "#C8102E"
GRIS = "#6B7079"
AMBAR = "#B7791F"
CRIT = -850.0


def _serie(puntos, kabs="abscisa", koff="off"):
    """(abscisas, offs) ordenadas; acepta dicts con off/off_mv/off_limpio."""
    xs, ys = [], []
    for p in puntos or []:
        a = p.get(kabs)
        off = p.get(koff)
        if off is None:
            off = p.get("off_mv") if p.get("off_mv") is not None else p.get("off_limpio")
        if isinstance(a, (int, float)) and isinstance(off, (int, float)):
            xs.append(a); ys.append(off)
    pares = sorted(zip(xs, ys))
    return [x for x, _ in pares], [y for _, y in pares]


def _stats(offs):
    if not offs:
        return {"n": 0, "pct_prot": None, "prom_off": None, "min_off": None,
                "max_off": None, "fuera": None}
    fuera = sum(1 for o in offs if o > CRIT)
    return {"n": len(offs), "fuera": fuera,
            "pct_prot": round(100 * (len(offs) - fuera) / len(offs), 1),
            "prom_off": round(sum(offs) / len(offs), 0),
            "min_off": round(min(offs), 0), "max_off": round(max(offs), 0)}


def _actual_offs(dfp):
    return [o for o in dfp["off"].tolist() if isinstance(o, (int, float))]


def resumen_comparativo(dfp, hist):
    """Devuelve {'actual':{...}, 'historico':{...}, 'periodo':str}."""
    act = _stats(_actual_offs(dfp))
    h = hist.get("resumen") or _stats(_serie(hist.get("puntos"))[1])
    return {"actual": act, "historico": h, "periodo": hist.get("periodo") or "histórico"}


def overlay_plotly(dfp, hist_puntos, periodo="histórico"):
    import plotly.graph_objects as go
    ax, ay = dfp["abscisa"].tolist(), dfp["off"].tolist()
    hx, hy = _serie(hist_puntos)
    fig = go.Figure()
    fig.add_hline(y=CRIT, line=dict(color=AMBAR, width=1.6, dash="dash"),
                  annotation_text="Criterio −850 mV", annotation_position="bottom right")
    fig.add_trace(go.Scatter(x=hx, y=hy, mode="lines", name=f"Histórico · {periodo}",
                             line=dict(color=GRIS, width=1)))
    fig.add_trace(go.Scatter(x=ax, y=ay, mode="lines", name="Inspección actual",
                             line=dict(color=ROJO, width=1.4)))
    fig.update_layout(
        height=430, margin=dict(l=10, r=10, t=30, b=10),
        yaxis=dict(title="Potencial OFF [mV]", autorange="reversed"),
        xaxis=dict(title="Abscisado (progresiva)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        plot_bgcolor="rgba(0,0,0,0)")
    fig.update_xaxes(gridcolor="#E3E5E9"); fig.update_yaxes(gridcolor="#E3E5E9")
    return fig


def _abscisa_txt(v):
    try:
        v = int(v); return f"K {v // 1000:03d}+{v % 1000:03d}"
    except (TypeError, ValueError):
        return str(v or "")


def _cabecera(fig, plt, tramo, sub, pag, total_pag):
    fig.text(0.06, 0.955, tramo, fontsize=15, fontweight="bold", color="#191C20")
    fig.text(0.06, 0.930, sub, fontsize=9.5, color="#646A73")
    fig.text(0.94, 0.955, "PCC Integrity", fontsize=12, fontweight="bold",
             color=ROJO, ha="right")
    fig.text(0.94, 0.932, f"Portal TGI · pág. {pag}/{total_pag}", fontsize=8,
             color="#646A73", ha="right")
    fig.add_artist(plt.Line2D([0.06, 0.94], [0.918, 0.918], color=ROJO, lw=2,
                              transform=fig.transFigure))


def _tabla(fig, plt, rect, titulo, colnames, filas, anchos=None, fs=7.5):
    ax = fig.add_axes(rect); ax.axis("off")
    if titulo:
        ax.text(0, 1.02, titulo, transform=ax.transAxes, fontsize=10,
                fontweight="bold", color="#191C20", va="bottom")
    if not filas:
        ax.text(0, 0.9, "Sin registros.", transform=ax.transAxes,
                fontsize=8.5, color="#9AA0A6", va="top")
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


def pdf_dashboard(detalle, dfp, hist=None) -> bytes:
    """PDF multipágina con TODO el dashboard CIPS (como se ve en el portal)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import Patch
    try:
        from dashboard import COLOR_ESTADO
    except Exception:
        COLOR_ESTADO = {}

    insp = detalle.get("inspeccion", {})
    hall = detalle.get("hallazgos", []) or []
    tramos = detalle.get("tramos", []) or []
    res = insp.get("resumen") or {}
    tramo = insp.get("tramo") or "Inspección"
    sub = f"Protección catódica (CIPS) · Dashboard de inspección"
    offs = [o for o in dfp["off"].tolist() if isinstance(o, (int, float))]
    pct = res.get("pct_cumple")
    if pct is None and offs:
        pct = round(100 * sum(1 for o in offs if o <= CRIT) / len(offs), 1)
    long_km = (res.get("longitud_m") or 0) / 1000
    NP = 4 if hist else 3

    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        # ── Página 1: resumen + KPIs + comparativa ───────────────────────────
        fig = plt.figure(figsize=(8.3, 11.7), dpi=150)     # A4 vertical
        _cabecera(fig, plt, tramo, sub, 1, NP)
        meta = [("Gasoducto", insp.get("gasoducto")), ("Fecha", insp.get("fecha")),
                ("Inspector", insp.get("inspector")), ("OT", insp.get("ot")),
                ("Ciclo", insp.get("ciclo")), ("Estado", insp.get("estado", "aprobada"))]
        y = 0.895
        for i, (k, v) in enumerate([m for m in meta if m[1]]):
            x = 0.06 + (i % 3) * 0.30
            if i % 3 == 0 and i:
                y -= 0.035
            fig.text(x, y, k.upper(), fontsize=7, color="#9AA0A6")
            fig.text(x, y - 0.016, str(v), fontsize=9.5, color="#191C20", fontweight="bold")
        # KPIs
        ky = y - 0.06
        kpis = [("Lecturas", res.get("total", len(dfp))),
                ("% Cumple ≤ −850 mV", f"{pct:.1f}%" if pct is not None else "—"),
                ("Longitud", f"{long_km:.2f} km" if long_km else "—"),
                ("Hallazgos", res.get("n_hallazgos", len(hall))),
                ("Tramos sin inspecc.", res.get("n_tramos_no_insp", len(tramos)))]
        for i, (k, v) in enumerate(kpis):
            x = 0.06 + i * 0.178
            fig.text(x, ky, str(v), fontsize=17, fontweight="bold", color=ROJO)
            fig.text(x, ky - 0.022, k, fontsize=7.2, color="#646A73")
        # Comparativa
        if hist:
            r = resumen_comparativo(dfp, hist); a, h = r["actual"], r["historico"]
            cy = ky - 0.065
            fig.text(0.06, cy, f"COMPARATIVA CON HISTÓRICO · {r['periodo']}",
                     fontsize=9.5, fontweight="bold", color="#191C20")
            comp = [("Tramo protegido", f"{h['pct_prot']}%", f"{a['pct_prot']}%"),
                    ("OFF promedio", f"{h['prom_off']:.0f} mV", f"{a['prom_off']:.0f} mV"),
                    ("Fuera de criterio", f"{h['fuera']}", f"{a['fuera']}"),
                    ("Puntos medidos", f"{h['n']}", f"{a['n']}")]
            for i, (k, was, now) in enumerate(comp):
                x = 0.06 + i * 0.225
                fig.text(x, cy - 0.03, k.upper(), fontsize=6.8, color="#9AA0A6")
                fig.text(x, cy - 0.05, f"{was} → ", fontsize=8.5, color="#646A73")
                fig.text(x + 0.075, cy - 0.052, now, fontsize=12, fontweight="bold",
                         color="#191C20")
            ax = fig.add_axes([0.09, 0.08, 0.85, cy - 0.13])
            hx, hy = _serie(hist.get("puntos"))
            ax.axhline(CRIT, color=AMBAR, lw=1.4, ls="--", label="Criterio −850 mV")
            ax.plot(hx, hy, color=GRIS, lw=.9, label=f"Histórico · {r['periodo']}")
            ax.plot(dfp["abscisa"].tolist(), dfp["off"].tolist(), color=ROJO, lw=1.1,
                    label="Inspección actual")
            ax.set_xlabel("Abscisado"); ax.set_ylabel("Potencial OFF [mV]")
            ax.invert_yaxis(); ax.grid(True, color="#E3E5E9", lw=.6); ax.set_axisbelow(True)
            for s in ("top", "right"): ax.spines[s].set_visible(False)
            ax.legend(loc="lower right", fontsize=8); ax.margins(x=.01)
        pdf.savefig(fig); plt.close(fig)

        # ── Página 2: mapa + gráficas ON/OFF y VAC ───────────────────────────
        fig = plt.figure(figsize=(8.3, 11.7), dpi=150)
        _cabecera(fig, plt, tramo, "Mapa y perfiles de potencial", 2, NP)
        mp = dfp.dropna(subset=["lat", "lon"])
        axm = fig.add_axes([0.08, 0.60, 0.86, 0.30])
        if not mp.empty:
            axm.scatter(mp["lon"], mp["lat"], c=mp["color"], s=10, edgecolors="none")
            axm.set_title("Mapa — estado de protección", fontsize=10, loc="left",
                          fontweight="bold", color="#191C20")
            axm.set_xlabel("Longitud"); axm.set_ylabel("Latitud")
            axm.grid(True, color="#EEF0F2", lw=.6); axm.set_axisbelow(True)
            leg = [Patch(color=COLOR_ESTADO.get(e, "#9CA3AF"), label=e)
                   for e in sorted(mp["estado"].unique())]
            axm.legend(handles=leg, fontsize=7.5, loc="best")
        else:
            axm.axis("off"); axm.text(0, .5, "Los puntos no tienen coordenadas.",
                                      fontsize=9, color="#9AA0A6")
        # ON/OFF
        axv = fig.add_axes([0.08, 0.33, 0.86, 0.20])
        axv.axhline(CRIT, color=AMBAR, lw=1.2, ls="--")
        axv.plot(dfp["abscisa"], dfp["on"], color="#2B5F8E", lw=.8, label="ON [mV]")
        axv.plot(dfp["abscisa"], dfp["off"], color=ROJO, lw=.9, label="OFF [mV]")
        axv.set_title("Potencial ON/OFF vs abscisa (VDC)", fontsize=10, loc="left",
                      fontweight="bold", color="#191C20")
        axv.set_ylabel("mV"); axv.invert_yaxis(); axv.grid(True, color="#E3E5E9", lw=.6)
        axv.set_axisbelow(True); axv.legend(fontsize=8, loc="lower right")
        for s in ("top", "right"): axv.spines[s].set_visible(False)
        # VAC
        axc = fig.add_axes([0.08, 0.07, 0.86, 0.18])
        if dfp["vac"].notna().any():
            axc.plot(dfp["abscisa"], dfp["vac"], color="#7A3FBF", lw=.9)
            axc.axhline(15, color=AMBAR, lw=1.1, ls="--", label="Límite 15 VAC")
            axc.set_title("Voltaje AC vs abscisa (VAC)", fontsize=10, loc="left",
                          fontweight="bold", color="#191C20")
            axc.set_xlabel("Abscisado"); axc.set_ylabel("VAC [V]")
            axc.grid(True, color="#E3E5E9", lw=.6); axc.set_axisbelow(True)
            axc.legend(fontsize=8)
            for s in ("top", "right"): axc.spines[s].set_visible(False)
        else:
            axc.axis("off"); axc.text(0, .5, "Sin datos de voltaje AC.",
                                      fontsize=9, color="#9AA0A6")
        pdf.savefig(fig); plt.close(fig)

        # ── Página 3: hallazgos + tramos no inspeccionados ───────────────────
        fig = plt.figure(figsize=(8.3, 11.7), dpi=150)
        _cabecera(fig, plt, tramo, "Hallazgos y tramos no inspeccionados", 3, NP)
        fh = [[_abscisa_txt(h.get("abscisa_ini")), h.get("tipo", ""),
               (h.get("descripcion", "") or "")[:70]] for h in hall]
        _tabla(fig, plt, [0.06, 0.52, 0.88, 0.36], f"Hallazgos ({len(hall)})",
               ["Abscisa", "Tipo", "Descripción"], fh, anchos=[0.18, 0.24, 0.58])
        ft = [[_abscisa_txt(t.get("abscisa_ini")), _abscisa_txt(t.get("abscisa_fin")),
               f"{t.get('longitud_m', '')}", (t.get("motivo", "") or "")[:60]]
              for t in tramos]
        _tabla(fig, plt, [0.06, 0.08, 0.88, 0.36],
               f"Tramos no inspeccionados ({len(tramos)})",
               ["Abscisa ini", "Abscisa fin", "Long [m]", "Motivo"], ft,
               anchos=[0.2, 0.2, 0.15, 0.45])
        pdf.savefig(fig); plt.close(fig)

        # ── Página 4: muestra de potenciales (solo las primeras filas) ───────
        MUESTRA = 40
        filas = []
        for _, p in dfp.head(MUESTRA).iterrows():
            filas.append([_abscisa_txt(p["abscisa"]),
                          f"{p['on']:.0f}" if isinstance(p["on"], (int, float)) else "",
                          f"{p['off']:.0f}" if isinstance(p["off"], (int, float)) else "",
                          f"{p['vac']:.1f}" if isinstance(p["vac"], (int, float)) else "",
                          str(p["estado"])])
        fig = plt.figure(figsize=(8.3, 11.7), dpi=150)
        _cabecera(fig, plt, tramo, f"Potenciales CIPS ({len(dfp)} lecturas)", 4, NP)
        _tabla(fig, plt, [0.10, 0.08, 0.80, 0.82],
               f"Muestra — primeras {min(MUESTRA, len(dfp))} de {len(dfp)} lecturas",
               ["Abscisa", "ON [mV]", "OFF [mV]", "VAC [V]", "Estado"], filas,
               anchos=[0.24, 0.19, 0.19, 0.15, 0.23], fs=7.5)
        fig.text(0.10, 0.05, "El detalle completo de lecturas está disponible en el "
                 "portal (dashboard interactivo) y en el informe del paquete de entrega.",
                 fontsize=7.5, color="#9AA0A6")
        pdf.savefig(fig); plt.close(fig)

    return buf.getvalue()


# compatibilidad: la comparativa suelta (una página)
def pdf_bytes(tramo, dfp, hist) -> bytes:
    return pdf_dashboard({"inspeccion": {"tramo": tramo}, "hallazgos": [],
                          "tramos": []}, dfp, hist)
