"""
Extrai séries do Banco Central (SGS) para o Espírito Santo e gera:
  - dados/fato_bacen_es.csv   -> formato longo (data, codigo, indicador, unidade, valor)
  - dados/painel_mensal_es.csv -> formato largo, 1 linha por mês (base do dash e do ML)

Uso:
    pip install -r requirements.txt
    python extrair_bacen_es.py                 # desde 2012
    python extrair_bacen_es.py --inicio 2004-01-01

Códigos validados em 11/2026 contra o histórico (PF + PJ = Total; inadimplência
total = média de PF e PJ ponderada pelo saldo). A API é pública e não exige chave.
"""
import argparse
import sys
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

# ---------------------------------------------------------------------------
# Catálogo de séries
# ---------------------------------------------------------------------------
SERIES = [
    # Espírito Santo
    {"codigo": 25399, "coluna": "ibcr_es_sa",        "nome": "IBCR-ES (com ajuste sazonal)",      "unidade": "índice",     "freq": "M"},
    {"codigo": 25398, "coluna": "ibcr_es",           "nome": "IBCR-ES (sem ajuste sazonal)",      "unidade": "índice",     "freq": "M"},
    {"codigo": 14009, "coluna": "saldo_pf_es",       "nome": "Saldo de crédito ES - PF",          "unidade": "R$ milhões", "freq": "M"},
    {"codigo": 14036, "coluna": "saldo_pj_es",       "nome": "Saldo de crédito ES - PJ",          "unidade": "R$ milhões", "freq": "M"},
    {"codigo": 14063, "coluna": "saldo_total_es",    "nome": "Saldo de crédito ES - Total",       "unidade": "R$ milhões", "freq": "M"},
    {"codigo": 15868, "coluna": "inad_pf_es",        "nome": "Inadimplência ES - PF (>90 dias)",  "unidade": "%",          "freq": "M"},
    {"codigo": 15900, "coluna": "inad_pj_es",        "nome": "Inadimplência ES - PJ (>90 dias)",  "unidade": "%",          "freq": "M"},
    {"codigo": 15932, "coluna": "inad_total_es",     "nome": "Inadimplência ES - Total (>90 dias)", "unidade": "%",        "freq": "M"},
    # Contexto nacional (variáveis explicativas para o ML)
    {"codigo": 432,   "coluna": "selic_meta",        "nome": "Meta Selic",                        "unidade": "% a.a.",     "freq": "D"},
    {"codigo": 433,   "coluna": "ipca_mensal",       "nome": "IPCA - variação mensal",            "unidade": "%",          "freq": "M"},
    {"codigo": 24364, "coluna": "ibcbr_sa",          "nome": "IBC-Br (com ajuste sazonal)",       "unidade": "índice",     "freq": "M"},
]
# Obs.: o BCB não publica taxa média de juros por UF no SGS; por isso não há "juros ES".

API = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"
PASTA = Path(__file__).parent / "dados"


def baixar_serie(codigo: int, inicio: date, fim: date, tentativas: int = 4) -> pd.DataFrame:
    """Baixa uma série em janelas de 10 anos (limite da API para séries diárias)."""
    partes = []
    ini = inicio
    while ini <= fim:
        fim_janela = min(date(ini.year + 9, 12, 31), fim)
        params = {
            "formato": "json",
            "dataInicial": ini.strftime("%d/%m/%Y"),
            "dataFinal": fim_janela.strftime("%d/%m/%Y"),
        }
        for t in range(tentativas):
            try:
                r = requests.get(API.format(codigo=codigo), params=params, timeout=60,
                                 headers={"Accept": "application/json"})
                if r.status_code == 404:          # janela sem dados
                    dados = []
                    break
                r.raise_for_status()
                if not r.text.lstrip().startswith("["):
                    raise ValueError(f"resposta não é JSON: {r.text[:120]!r}")
                dados = r.json()
                break
            except Exception as e:
                if t == tentativas - 1:
                    raise RuntimeError(f"série {codigo}: {e}") from e
                time.sleep(2 ** (t + 1))
        partes.extend(dados)
        ini = date(fim_janela.year + 1, 1, 1)

    df = pd.DataFrame(partes)
    if df.empty:
        return pd.DataFrame(columns=["data", "valor"])
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = pd.to_numeric(df["valor"].astype(str).str.replace(",", "."), errors="coerce")
    return df.dropna().drop_duplicates("data").sort_values("data")


def validar(painel: pd.DataFrame) -> list[str]:
    avisos = []
    hoje = pd.Timestamp.today()
    for s in SERIES:
        col = painel[s["coluna"]].dropna()
        if col.empty:
            avisos.append(f"[ERRO] {s['codigo']} {s['nome']}: sem dados")
            continue
        atraso = (hoje - col.index.max()).days
        if atraso > 200:
            avisos.append(f"[AVISO] {s['codigo']} {s['nome']}: último dado {col.index.max():%m/%Y} (série parada?)")
    # Consistência contábil
    p = painel.dropna(subset=["saldo_pf_es", "saldo_pj_es", "saldo_total_es"])
    erro = (p.saldo_pf_es + p.saldo_pj_es - p.saldo_total_es).abs().max()
    if erro > 2:
        avisos.append(f"[AVISO] PF + PJ difere do total em até R$ {erro:.0f} mi - conferir códigos")
    return avisos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inicio", default="2012-01-01", help="AAAA-MM-DD")
    args = ap.parse_args()
    inicio = datetime.strptime(args.inicio, "%Y-%m-%d").date()
    fim = date.today()
    PASTA.mkdir(exist_ok=True)

    longos, mensais = [], {}
    for s in SERIES:
        print(f"Baixando {s['codigo']:>6}  {s['nome']} ...", end=" ", flush=True)
        try:
            df = baixar_serie(s["codigo"], inicio, fim)
        except Exception as e:
            print(f"FALHOU ({e})")
            continue
        print(f"{len(df)} registros")
        df["codigo"], df["indicador"], df["unidade"] = s["codigo"], s["nome"], s["unidade"]
        longos.append(df)
        serie = df.set_index("data")["valor"]
        # Diárias -> valor do fim do mês; mensais -> padroniza no 1º dia do mês
        serie = serie.resample("MS").last() if s["freq"] == "D" else serie.resample("MS").mean()
        mensais[s["coluna"]] = serie
        time.sleep(0.3)

    if not longos:
        sys.exit("Nenhuma série baixada. Verifique sua conexão com api.bcb.gov.br.")

    fato = pd.concat(longos)[["data", "codigo", "indicador", "unidade", "valor"]]
    fato.to_csv(PASTA / "fato_bacen_es.csv", index=False)

    painel = pd.DataFrame(mensais)
    painel.index.name = "mes"
    for s in SERIES:  # garante todas as colunas mesmo se alguma falhou
        painel[s["coluna"]] = painel.get(s["coluna"])
    painel = painel[[s["coluna"] for s in SERIES]]
    # IPCA acumulado em 12 meses (útil para dash e ML)
    painel["ipca_12m"] = ((1 + painel.ipca_mensal / 100).rolling(12).apply(lambda x: x.prod()) - 1) * 100
    painel.to_csv(PASTA / "painel_mensal_es.csv")

    print(f"\nArquivos salvos em {PASTA}/")
    print(f"  fato_bacen_es.csv    {len(fato):>6} linhas (formato longo)")
    print(f"  painel_mensal_es.csv {len(painel):>6} meses ({painel.index.min():%m/%Y} a {painel.index.max():%m/%Y})")
    for a in validar(painel):
        print(a)


if __name__ == "__main__":
    main()
