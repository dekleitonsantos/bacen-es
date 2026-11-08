/**
 * Carrega séries do Banco Central (SGS) do Espírito Santo para a aba "fato_bacen_es".
 * Colar em: Planilha > Extensões > Apps Script. Rodar "carregarSeriesBacenParaDrive".
 *
 * Códigos validados em 11/2026 (ver CONTEXTO_PARA_CLAUDE.md).
 * Se o log mostrar erro em TODAS as séries (inclusive a Selic 432), o Banco Central
 * está bloqueando os servidores do Google -> use o pipeline Python ou um proxy.
 */
const SERIES_BACEN_ES = [
  { codigo: 25399, nome: 'IBCR_ES_dessaz',       unidade: 'indice' },
  { codigo: 25398, nome: 'IBCR_ES',              unidade: 'indice' },
  { codigo: 14009, nome: 'Saldo_Credito_PF_ES',  unidade: 'R$ milhoes' },
  { codigo: 14036, nome: 'Saldo_Credito_PJ_ES',  unidade: 'R$ milhoes' },
  { codigo: 14063, nome: 'Saldo_Credito_Total_ES', unidade: 'R$ milhoes' },
  { codigo: 15868, nome: 'Inadimplencia_PF_ES',  unidade: '%' },
  { codigo: 15900, nome: 'Inadimplencia_PJ_ES',  unidade: '%' },
  { codigo: 15932, nome: 'Inadimplencia_Total_ES', unidade: '%' },
  { codigo: 433,   nome: 'IPCA_mensal',          unidade: '%' },
  { codigo: 24364, nome: 'IBC_Br_dessaz',        unidade: 'indice' },
];
const MESES = 60; // últimos N registros de cada série

function carregarSeriesBacenParaDrive() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('fato_bacen_es') || ss.insertSheet('fato_bacen_es');
  const log = ss.getSheetByName('log_bacen') || ss.insertSheet('log_bacen');
  const linhas = [], logs = [];

  SERIES_BACEN_ES.forEach(s => {
    const url = `https://api.bcb.gov.br/dados/serie/bcdata.sgs.${s.codigo}/dados/ultimos/${MESES}?formato=json`;
    try {
      const resp = UrlFetchApp.fetch(url, { muteHttpExceptions: true, headers: { Accept: 'application/json' } });
      const status = resp.getResponseCode(), corpo = resp.getContentText();
      if (status !== 200 || !corpo.trim().startsWith('[')) {
        logs.push([new Date(), s.codigo, s.nome, 'ERRO', `HTTP ${status}: ${corpo.slice(0, 150)}`]);
        return;
      }
      const dados = JSON.parse(corpo);
      dados.forEach(item => {
        const [d, m, a] = item.data.split('/');
        const valor = parseFloat(String(item.valor).replace(',', '.'));
        if (!isNaN(valor)) linhas.push([new Date(+a, +m - 1, +d), s.codigo, s.nome, s.unidade, valor]);
      });
      logs.push([new Date(), s.codigo, s.nome, 'OK', `${dados.length} registros`]);
    } catch (e) {
      logs.push([new Date(), s.codigo, s.nome, 'ERRO', e.message]);
    }
    Utilities.sleep(500);
  });

  if (linhas.length) {
    sheet.clear();
    sheet.getRange(1, 1, 1, 5).setValues([['data', 'codigo_serie', 'indicador', 'unidade', 'valor']]);
    sheet.getRange(2, 1, linhas.length, 5).setValues(linhas);
    sheet.getRange(2, 1, linhas.length, 1).setNumberFormat('yyyy-mm');
  }
  if (log.getLastRow() === 0) log.appendRow(['executado_em', 'codigo', 'indicador', 'status', 'detalhe']);
  log.getRange(log.getLastRow() + 1, 1, logs.length, 5).setValues(logs);
}

/** Teste rápido: o Apps Script consegue acessar a API do BCB? Ver Registro de execução. */
function testarAcessoBacen() {
  const r = UrlFetchApp.fetch('https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados/ultimos/3?formato=json',
                              { muteHttpExceptions: true });
  Logger.log(`${r.getResponseCode()}\n${r.getContentText().slice(0, 200)}`);
}
