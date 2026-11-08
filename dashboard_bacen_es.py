"""
Gera dashboard_bacen_es.html (abre em qualquer navegador) a partir de dados/painel_mensal_es.csv.

Uso:
    python extrair_bacen_es.py   # 1º: baixa os dados
    python dashboard_bacen_es.py
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

BASE = Path(__file__).parent
p = pd.read_csv(BASE / "dados" / "painel_mensal_es.csv", parse_dates=["mes"], index_col="mes")

AZUL, CINZA, VERDE, ROXO = "#2563eb", "#64748b", "#16a34a", "#9333ea"
PF, PJ = "#0d9488", "#d97706"   # mesma cor para PF/PJ em crédito e inadimplência


def ultimo(col):
    s = p[col].dropna()
    return s.index[-1], s.iloc[-1], s


def var_anual(col):
    data, v, s = ultimo(col)
    ant = s.get(data - pd.DateOffset(years=1))
    return (v / ant - 1) * 100 if ant else None


# ---------------- KPIs ----------------
d_ibcr, ibcr, _ = ultimo("ibcr_es_sa")
d_cred, cred, _ = ultimo("saldo_total_es")
d_inad, inad, s_inad = ultimo("inad_total_es")
inad_ant = s_inad.get(d_inad - pd.DateOffset(years=1))
_, selic, _ = ultimo("selic_meta")

kpis = [
    ("IBCR-ES (dessaz.)", f"{ibcr:.1f}", f"{var_anual('ibcr_es_sa'):+.1f}% em 12 meses", f"{d_ibcr:%m/%Y}"),
    ("Saldo de crédito ES", f"R$ {cred/1000:.1f} bi", f"{var_anual('saldo_total_es'):+.1f}% em 12 meses", f"{d_cred:%m/%Y}"),
    ("Inadimplência ES", f"{inad:.2f}%", f"{inad - inad_ant:+.2f} p.p. em 12 meses", f"{d_inad:%m/%Y}"),
    ("Meta Selic", f"{selic:.2f}%", "ao ano", "atual"),
]

# ---------------- Gráficos ----------------
fig = make_subplots(
    rows=2, cols=2, vertical_spacing=0.14, horizontal_spacing=0.08,
    subplot_titles=("Atividade econômica: IBCR-ES vs IBC-Br (dessaz.)",
                    "Saldo de crédito no ES (R$ bilhões)",
                    "Inadimplência > 90 dias no ES (%)",
                    "Juros e inflação nacionais (%)"),
)
ibc = p[["ibcr_es_sa", "ibcbr_sa"]].dropna()
fig.add_scatter(x=ibc.index, y=ibc.ibcr_es_sa, name="IBCR-ES", line_color=AZUL, row=1, col=1)
fig.add_scatter(x=ibc.index, y=ibc.ibcbr_sa, name="IBC-Br", line=dict(color=CINZA, dash="dot"), row=1, col=1)

cr = p[["saldo_pf_es", "saldo_pj_es"]].dropna()
fig.add_scatter(x=cr.index, y=cr.saldo_pf_es / 1000, name="Crédito PF", stackgroup="c", line_color=PF, row=1, col=2)
fig.add_scatter(x=cr.index, y=cr.saldo_pj_es / 1000, name="Crédito PJ", stackgroup="c", line_color=PJ, row=1, col=2)

fig.add_scatter(x=p.index, y=p.inad_pf_es, name="Inad. PF", line_color=PF, row=2, col=1)
fig.add_scatter(x=p.index, y=p.inad_pj_es, name="Inad. PJ", line_color=PJ, row=2, col=1)
fig.add_scatter(x=p.index, y=p.inad_total_es, name="Inad. Total", line=dict(color="#111827", width=3), row=2, col=1)

fig.add_scatter(x=p.index, y=p.selic_meta, name="Meta Selic", line_color=VERDE, row=2, col=2)
fig.add_scatter(x=p.index, y=p.ipca_12m, name="IPCA 12m", line_color=ROXO, row=2, col=2)

fig.update_layout(height=820, template="plotly_white", hovermode="x unified",
                  legend=dict(orientation="h", y=-0.08), margin=dict(t=40, l=40, r=20, b=40),
                  font=dict(family="Inter, Segoe UI, sans-serif"))

cards = "".join(
    f'<div class="card"><div class="t">{t}</div><div class="v">{v}</div>'
    f'<div class="s">{s}</div><div class="d">ref. {d}</div></div>' for t, v, s, d in kpis
)
html = f"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Crédito e Atividade ES</title>
<style>
 body{{font-family:Inter,Segoe UI,sans-serif;background:#f8fafc;color:#0f172a;margin:0;padding:24px}}
 h1{{margin:0 0 4px;font-size:22px}} .sub{{color:#64748b;margin-bottom:20px;font-size:14px}}
 .kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin-bottom:16px}}
 .card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px}}
 .t{{font-size:13px;color:#64748b}} .v{{font-size:26px;font-weight:700;margin:4px 0}}
 .s{{font-size:13px}} .d{{font-size:11px;color:#94a3b8;margin-top:4px}}
 .graf{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:8px}}
</style></head><body>
<h1>Crédito e Atividade Econômica no Espírito Santo</h1>
<div class="sub">Fonte: Banco Central do Brasil - SGS (séries 25399, 14009/14036/14063, 15868/15900/15932, 432, 433, 24364)</div>
<div class="kpis">{cards}</div>
<div class="graf">{fig.to_html(full_html=False, include_plotlyjs=True)}</div>
</body></html>"""

saida = BASE / "dashboard_bacen_es.html"
saida.write_text(html, encoding="utf-8")
print(f"Dashboard salvo em {saida}")
