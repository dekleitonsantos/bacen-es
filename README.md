# Crédito e Atividade Econômica no Espírito Santo — dados do Banco Central

Pipeline em Python: **API do Banco Central (SGS) → CSV → dashboard + modelo de ML**.

## Como rodar
```bash
pip install -r requirements.txt
python extrair_bacen_es.py      # baixa as séries -> dados/*.csv
python dashboard_bacen_es.py    # gera dashboard_bacen_es.html
python modelo_ml_bacen_es.py    # treina e avalia o modelo de inadimplência
```

## Séries usadas (validadas)
| Código | Série | Unidade |
|---|---|---|
| 25399 / 25398 | IBCR-ES com / sem ajuste sazonal | índice |
| 14009 / 14036 / 14063 | Saldo de crédito ES — PF / PJ / Total | R$ milhões |
| 15868 / 15900 / 15932 | Inadimplência >90 dias ES — PF / PJ / Total | % |
| 432 | Meta Selic | % a.a. |
| 433 | IPCA mensal | % |
| 24364 | IBC-Br dessazonalizado | índice |

Validação: PF + PJ = Total do saldo em todos os meses; a inadimplência total é igual à
média de PF e PJ ponderada pelo saldo (erro < 0,01 p.p.).

## Arquivos gerados
- `dados/fato_bacen_es.csv` — formato longo (para Sheets / Power BI / Looker Studio)
- `dados/painel_mensal_es.csv` — 1 linha por mês, 1 coluna por série (base do ML)
- `dados/previsoes_backtest.csv` — previsões vs. realizado do backtest
- `dashboard_bacen_es.html` — dashboard interativo

## Resultado do modelo
Previsão da inadimplência total do ES 3 meses à frente, com validação walk-forward
(5 janelas de 12 meses). Até agora o baseline ingênuo ("daqui a 3 meses será igual a hoje")
ainda supera os modelos testados: a inadimplência é muito persistente.
