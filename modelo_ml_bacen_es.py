"""
Modelo de ML: prevê a inadimplência total do ES daqui a H meses
a partir de crédito, atividade econômica, Selic e inflação.

Uso:
    python extrair_bacen_es.py      # 1º: baixa os dados
    python modelo_ml_bacen_es.py    # treina, avalia e salva previsões

Boas práticas de série temporal aplicadas:
  - só usa informação disponível ATÉ o mês t para prever t+H (sem vazamento)
  - validação walk-forward (TimeSeriesSplit), nunca embaralha os meses
  - compara com baseline ingênuo ("a inadimplência daqui a H meses = a de hoje")
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import RidgeCV
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

HORIZONTE = 3          # meses à frente
ALVO = "inad_total_es"
BASE = Path(__file__).parent

p = pd.read_csv(BASE / "dados" / "painel_mensal_es.csv", parse_dates=["mes"], index_col="mes")

# ---------------- Engenharia de features ----------------
X = pd.DataFrame(index=p.index)
X["inad_total"] = p.inad_total_es
X["inad_pf"] = p.inad_pf_es
X["inad_pj"] = p.inad_pj_es
X["inad_var_3m"] = p.inad_total_es.diff(3)
X["inad_var_12m"] = p.inad_total_es.diff(12)
X["credito_yoy"] = p.saldo_total_es.pct_change(12) * 100
X["credito_pf_share"] = p.saldo_pf_es / p.saldo_total_es
X["credito_var_3m"] = p.saldo_total_es.pct_change(3) * 100
X["ibcr_yoy"] = p.ibcr_es_sa.pct_change(12) * 100
X["ibcr_var_3m"] = p.ibcr_es_sa.pct_change(3) * 100
X["selic"] = p.selic_meta
X["selic_var_12m"] = p.selic_meta.diff(12)
X["ipca_12m"] = p.ipca_12m
X["juro_real"] = p.selic_meta - p.ipca_12m
X["mes_do_ano"] = p.index.month

# O IBCR sai ~1 mês depois do crédito; preenche o último mês para não perder a linha mais recente
X[["ibcr_yoy", "ibcr_var_3m"]] = X[["ibcr_yoy", "ibcr_var_3m"]].ffill(limit=2)

# Alvo: VARIAÇÃO da inadimplência entre t e t+H. Prever a variação (e somar ao nível atual)
# funciona bem melhor que prever o nível: a série é muito persistente e árvores não extrapolam níveis.
y = p[ALVO].shift(-HORIZONTE) - p[ALVO]
dados = X.join(y.rename("alvo")).dropna(subset=X.columns.drop("mes_do_ano").tolist())
treino = dados.dropna(subset=["alvo"])
ultimo_mes = dados[dados.alvo.isna()].tail(1)   # mês mais recente, ainda sem alvo -> previsão futura

feats = X.columns.tolist()
modelos = {
    "Ridge (linear)": make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-2, 3, 30))),
    "Gradient Boosting": GradientBoostingRegressor(n_estimators=300, max_depth=2, learning_rate=0.03,
                                                   subsample=0.8, random_state=42),
}

# ---------------- Validação walk-forward ----------------
tscv = TimeSeriesSplit(n_splits=5, test_size=12)
resultados = {nome: [] for nome in modelos} | {"Baseline ingênuo": []}
previsoes = []
for i, (tr, te) in enumerate(tscv.split(treino)):
    Xtr, Xte = treino.iloc[tr][feats], treino.iloc[te][feats]
    ytr = treino.iloc[tr].alvo
    yte = treino.iloc[te].alvo + Xte.inad_total          # nível real em t+H
    resultados["Baseline ingênuo"].append(mean_absolute_error(yte, Xte.inad_total))
    for nome, m in modelos.items():
        m.fit(Xtr, ytr)
        pred = Xte.inad_total.values + m.predict(Xte)    # nível atual + variação prevista
        resultados[nome].append(mean_absolute_error(yte, pred))
        previsoes.append(pd.DataFrame({"mes_base": Xte.index, "mes_alvo": Xte.index + pd.DateOffset(months=HORIZONTE),
                                       "modelo": nome, "real": yte.values, "previsto": pred, "fold": i}))

print(f"Previsão da inadimplência total do ES {HORIZONTE} meses à frente")
print(f"Amostra de treino: {treino.index.min():%m/%Y} a {treino.index.max():%m/%Y} ({len(treino)} meses)\n")
print("Erro absoluto médio (p.p.) em 5 janelas de 12 meses:")
for nome, erros in sorted(resultados.items(), key=lambda kv: np.mean(kv[1])):
    print(f"  {nome:<20} {np.mean(erros):.3f}  (por janela: {', '.join(f'{e:.2f}' for e in erros)})")

# ---------------- Modelo final + previsão futura ----------------
melhor = min(modelos, key=lambda n: np.mean(resultados[n]))
m = modelos[melhor].fit(treino[feats], treino.alvo)
if not ultimo_mes.empty:
    prev = ultimo_mes.inad_total.iloc[0] + m.predict(ultimo_mes[feats])[0]
    base = ultimo_mes.index[0]
    ganhou = np.mean(resultados[melhor]) < np.mean(resultados["Baseline ingênuo"])
    print(f"\nMelhor modelo: {melhor} " + ("(supera o baseline)" if ganhou else
          "(NÃO supera o baseline - trate a previsão com cautela)"))
    print(f"Inadimplência em {base:%m/%Y}: {ultimo_mes.inad_total.iloc[0]:.2f}%  ->  "
          f"previsão para {base + pd.DateOffset(months=HORIZONTE):%m/%Y}: {prev:.2f}%")

if melhor == "Gradient Boosting":
    imp = pd.Series(m.feature_importances_, feats).sort_values(ascending=False)
    print("\nVariáveis mais importantes:")
    print(imp.head(8).round(3).to_string())
else:
    coef = pd.Series(m[-1].coef_, feats).sort_values(key=abs, ascending=False)
    print("\nMaiores coeficientes (variáveis padronizadas):")
    print(coef.head(8).round(3).to_string())

(BASE / "dados").mkdir(exist_ok=True)
pd.concat(previsoes).to_csv(BASE / "dados" / "previsoes_backtest.csv", index=False)
print(f"\nBacktest salvo em dados/previsoes_backtest.csv")
