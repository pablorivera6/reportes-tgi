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


def pdf_bytes(tramo, dfp, hist) -> bytes:
    """PDF de una página con la comparativa (matplotlib)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ax_x, ax_y = dfp["abscisa"].tolist(), dfp["off"].tolist()
    hx, hy = _serie(hist.get("puntos"))
    r = resumen_comparativo(dfp, hist)
    a, h = r["actual"], r["historico"]

    fig = plt.figure(figsize=(11.7, 8.3), dpi=150)      # A4 apaisado
    fig.subplots_adjust(left=0.08, right=0.96, top=0.80, bottom=0.10)

    fig.text(0.08, 0.945, "Comparativa histórico vs. inspección actual",
             fontsize=17, fontweight="bold", color="#191C20")
    fig.text(0.08, 0.915, f"Protección catódica (CIPS)  ·  {tramo}",
             fontsize=11, color="#646A73")
    fig.text(0.96, 0.945, "PCC Integrity", fontsize=13, fontweight="bold",
             color=ROJO, ha="right")
    fig.text(0.96, 0.918, f"Histórico ({r['periodo']})  vs  Inspección actual",
             fontsize=9, color="#646A73", ha="right")
    fig.add_artist(plt.Line2D([0.08, 0.96], [0.90, 0.90], color=ROJO,
                              lw=2, transform=fig.transFigure))

    # Fila de métricas
    def metric(x, label, was, now, color="#191C20"):
        fig.text(x, 0.855, label, fontsize=8.5, color="#646A73",
                 transform=fig.transFigure)
        fig.text(x, 0.822, f"{was}  →  ", fontsize=11, color="#646A73",
                 transform=fig.transFigure)
        fig.text(x + 0.052, 0.818, f"{now}", fontsize=15, fontweight="bold",
                 color=color, transform=fig.transFigure)
    trend = "#1E8A5B" if (a["prom_off"] or 0) < (h["prom_off"] or 0) else ROJO
    metric(0.08, "TRAMO PROTEGIDO", f"{h['pct_prot']}%", f"{a['pct_prot']}%",
           "#1E8A5B" if (a["fuera"] or 0) <= (h["fuera"] or 0) else ROJO)
    metric(0.31, "OFF PROMEDIO [mV]", f"{h['prom_off']:.0f}", f"{a['prom_off']:.0f}", trend)
    metric(0.55, "PUNTOS FUERA DE CRITERIO", f"{h['fuera']}", f"{a['fuera']}",
           "#1E8A5B" if (a["fuera"] or 0) <= (h["fuera"] or 0) else ROJO)
    metric(0.78, "PUNTOS MEDIDOS", f"{h['n']}", f"{a['n']}")

    ax = fig.add_axes([0.08, 0.10, 0.88, 0.62])
    ax.axhline(CRIT, color=AMBAR, lw=1.6, ls="--", label="Criterio NACE (−850 mV)")
    ax.plot(hx, hy, color=GRIS, lw=1.0, label=f"Histórico · {r['periodo']}")
    ax.plot(ax_x, ax_y, color=ROJO, lw=1.2, label="Inspección actual")
    ax.fill_between(ax_x, ax_y, CRIT, where=[o > CRIT for o in ax_y],
                    color=ROJO, alpha=.18)
    ax.set_xlabel("Abscisado (progresiva)"); ax.set_ylabel("Potencial OFF [mV]")
    ax.invert_yaxis(); ax.grid(True, color="#E3E5E9", lw=.7); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(loc="lower right", fontsize=9, framealpha=.95)
    ax.margins(x=0.01)

    buf = io.BytesIO()
    fig.savefig(buf, format="pdf")
    plt.close(fig)
    return buf.getvalue()
