import { execFile } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import { promisify } from "node:util";
import path from "node:path";
import process from "node:process";
import sql from "mssql";
import sharp from "sharp";

const execFileAsync = promisify(execFile);

const UNITS = ["ANJINHO", "BARIGUI", "CHAMPAGNAT", "ECOVILLE", "SANTA FELICIDADE"];
const DEFAULT_TARGET = "-5491953098";
const OUT_DIR = "/home/node/.openclaw/workspace/agenda-digital/out";

function argValue(name, fallback = "") {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] || fallback : fallback;
}

function flag(name) {
  return process.argv.includes(name);
}

function brNumber(value) {
  return Number(value || 0).toLocaleString("pt-BR");
}

function escapeXml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function nowInBrazil() {
  return new Intl.DateTimeFormat("pt-BR", {
    timeZone: "America/Sao_Paulo",
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date());
}

async function connect() {
  const env = process.env;
  const sslMode = (env.TICKETS_DB_SSLMODE || "prefer").toLowerCase();
  return sql.connect({
    server: env.TICKETS_DB_HOST,
    port: Number(env.TICKETS_DB_PORT || 1433),
    database: env.TICKETS_DB_NAME,
    user: env.TICKETS_DB_USER,
    password: env.TICKETS_DB_PASSWORD,
    options: {
      encrypt: ["require", "verify-full", "verify-ca"].includes(sslMode),
      trustServerCertificate: !["verify-full", "verify-ca"].includes(sslMode),
      enableArithAbort: true,
    },
    pool: { max: 2, min: 0, idleTimeoutMillis: 10000 },
    connectionTimeout: 15000,
    requestTimeout: 30000,
  });
}

async function loadData(pool) {
  const agenda = await pool.request().query(`
    select
      u_name as unidade,
      count(*) as total,
      sum(case when st_name = 'EM ABERTO' then 1 else 0 end) as abertas,
      sum(case when FechamentoAtrasado = 'Sim' then 1 else 0 end) as atrasadas,
      sum(case when SemPresentes = 'Sim' then 1 else 0 end) as sem_presentes,
      max(coalesce(modified, created, data_atualizacao)) as ultima_atualizacao
    from dbo.TMP_DADOS_FAT_AGENDA2026
    where u_name in ('ANJINHO', 'BARIGUI', 'CHAMPAGNAT', 'ECOVILLE', 'SANTA FELICIDADE')
    group by u_name
  `);

  const comunicacao = await pool.request().query(`
    select
      filial as unidade,
      count(*) as total,
      sum(case when Fechado = 'NÃO' then 1 else 0 end) as abertas,
      sum(case when Fechado = 'NÃO' and status = 'AGUARDANDO RETORNO DO PROFESSOR(A)' then 1 else 0 end) as abertas_professor,
      sum(case when Fechado = 'NÃO' and status = 'AGUARDANDO RETORNO DO RESPONSÁVEL' then 1 else 0 end) as abertas_responsavel,
      max(DataCriacao) as ultima_criacao
    from dbo.TMP_DADOS_FAT_COMUNICACAO2026
    where filial in ('ANJINHO', 'BARIGUI', 'CHAMPAGNAT', 'ECOVILLE', 'SANTA FELICIDADE')
    group by filial
  `);

  const recentOpen = await pool.request().query(`
    select top (8)
      COD,
      convert(varchar(10), DataCriacao, 103) + ' ' + left(convert(varchar(8), DataCriacao, 108), 5) as DataCriacaoBR,
      status,
      filial,
      DESCTURMA,
      Usuarioabertura
    from dbo.TMP_DADOS_FAT_COMUNICACAO2026
    where Fechado = 'NÃO'
    order by DataCriacao desc
  `);

  return {
    agenda: new Map(agenda.recordset.map((row) => [row.unidade, row])),
    comunicacao: new Map(comunicacao.recordset.map((row) => [row.unidade, row])),
    recentOpen: recentOpen.recordset,
  };
}

function renderSvg(data) {
  const rows = UNITS.map((unit, index) => {
    const agenda = data.agenda.get(unit) || {};
    const comunicacao = data.comunicacao.get(unit) || {};
    const y = 246 + index * 118;
    const alert = Number(agenda.abertas || 0) + Number(comunicacao.abertas || 0);
    const fill = alert > 0 ? "#FFF8D8" : "#ECFDF3";
    const stroke = alert > 0 ? "#F7C600" : "#57D68D";
    return `
      <rect x="42" y="${y}" width="1116" height="92" rx="18" fill="${fill}" stroke="${stroke}" stroke-width="3"/>
      <text x="72" y="${y + 34}" class="unit">${escapeXml(unit)}</text>
      <text x="72" y="${y + 66}" class="muted">Agenda: ${brNumber(agenda.total)} registros</text>
      <text x="362" y="${y + 39}" class="metric">${brNumber(agenda.abertas)} abertas</text>
      <text x="542" y="${y + 39}" class="metric">${brNumber(agenda.atrasadas)} atrasadas</text>
      <text x="742" y="${y + 39}" class="metric">${brNumber(agenda.sem_presentes)} sem presentes</text>
      <text x="362" y="${y + 68}" class="muted">Comunicações abertas: ${brNumber(comunicacao.abertas)}</text>
      <text x="642" y="${y + 68}" class="muted">Professor: ${brNumber(comunicacao.abertas_professor)} | Responsável: ${brNumber(comunicacao.abertas_responsavel)}</text>
    `;
  }).join("");

  const totalAgendaAberta = UNITS.reduce((sum, unit) => sum + Number(data.agenda.get(unit)?.abertas || 0), 0);
  const totalAgendaAtrasada = UNITS.reduce((sum, unit) => sum + Number(data.agenda.get(unit)?.atrasadas || 0), 0);
  const totalComunicacaoAberta = UNITS.reduce((sum, unit) => sum + Number(data.comunicacao.get(unit)?.abertas || 0), 0);

  return `<?xml version="1.0" encoding="UTF-8"?>
  <svg width="1200" height="900" viewBox="0 0 1200 900" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <style>
        .title { font: 800 42px Arial, sans-serif; fill: #252C64; }
        .subtitle { font: 500 22px Arial, sans-serif; fill: #4B588A; }
        .cardTitle { font: 800 24px Arial, sans-serif; fill: #252C64; }
        .cardValue { font: 900 40px Arial, sans-serif; fill: #0B1437; }
        .unit { font: 800 24px Arial, sans-serif; fill: #0B1437; }
        .metric { font: 800 21px Arial, sans-serif; fill: #0B1437; }
        .muted { font: 500 17px Arial, sans-serif; fill: #415072; }
        .footer { font: 500 16px Arial, sans-serif; fill: #4B588A; }
      </style>
    </defs>
    <rect width="1200" height="900" fill="#F4F7FB"/>
    <rect x="0" y="0" width="1200" height="156" fill="#252C64"/>
    <rect x="0" y="156" width="1200" height="10" fill="#FFC400"/>
    <text x="42" y="70" class="title" fill="#FFFFFF">Automação Agenda Digital V1</text>
    <text x="42" y="112" class="subtitle" fill="#FFFFFF">Rede de Colégios Santo Anjo · ${escapeXml(nowInBrazil())}</text>

    <rect x="42" y="188" width="350" height="72" rx="16" fill="#FFFFFF" stroke="#D8DFEF"/>
    <text x="66" y="218" class="cardTitle">Agendas abertas</text>
    <text x="66" y="252" class="cardValue">${brNumber(totalAgendaAberta)}</text>

    <rect x="424" y="188" width="350" height="72" rx="16" fill="#FFFFFF" stroke="#D8DFEF"/>
    <text x="448" y="218" class="cardTitle">Fechamentos atrasados</text>
    <text x="448" y="252" class="cardValue">${brNumber(totalAgendaAtrasada)}</text>

    <rect x="806" y="188" width="352" height="72" rx="16" fill="#FFFFFF" stroke="#D8DFEF"/>
    <text x="830" y="218" class="cardTitle">Comunicações abertas</text>
    <text x="830" y="252" class="cardValue">${brNumber(totalComunicacaoAberta)}</text>

    ${rows}

    <text x="42" y="864" class="footer">Fonte: BI_ACADEMICO · TMP_DADOS_FAT_AGENDA2026 e TMP_DADOS_FAT_COMUNICACAO2026 · consulta somente leitura</text>
  </svg>`;
}

function buildSummary(data, imagePath) {
  const totalAgendaAberta = UNITS.reduce((sum, unit) => sum + Number(data.agenda.get(unit)?.abertas || 0), 0);
  const totalAgendaAtrasada = UNITS.reduce((sum, unit) => sum + Number(data.agenda.get(unit)?.atrasadas || 0), 0);
  const totalComunicacaoAberta = UNITS.reduce((sum, unit) => sum + Number(data.comunicacao.get(unit)?.abertas || 0), 0);
  const lines = [
    "Automação Agenda Digital V1 executada.",
    "",
    `Agendas abertas: ${brNumber(totalAgendaAberta)}`,
    `Fechamentos atrasados: ${brNumber(totalAgendaAtrasada)}`,
    `Comunicações abertas: ${brNumber(totalComunicacaoAberta)}`,
    "",
    "Unidades analisadas: " + UNITS.join(", ") + ".",
    `Imagem gerada: ${imagePath}`,
  ];

  if (data.recentOpen.length) {
    lines.push("", "Comunicações abertas mais recentes:");
    for (const item of data.recentOpen.slice(0, 5)) {
      lines.push(`- ${item.filial}: ${item.COD} · ${item.status} · ${item.DataCriacaoBR}`);
    }
  }

  return lines.join("\n");
}

async function sendTelegram(target, message, mediaPath) {
  await execFileAsync("openclaw", [
    "message",
    "send",
    "--channel",
    "telegram",
    "--target",
    target,
    "--message",
    message,
    "--media",
    mediaPath,
    "--force-document",
  ], { maxBuffer: 1024 * 1024 * 5 });
}

await mkdir(OUT_DIR, { recursive: true });

const pool = await connect();
try {
  const data = await loadData(pool);
  const stamp = new Date().toISOString().replaceAll(":", "-").slice(0, 19);
  const svgPath = path.join(OUT_DIR, `agenda-digital-v1-${stamp}.svg`);
  const pngPath = path.join(OUT_DIR, `agenda-digital-v1-${stamp}.png`);
  await writeFile(svgPath, renderSvg(data), "utf8");
  await sharp(svgPath).png().toFile(pngPath);

  const summary = buildSummary(data, pngPath);
  console.log(summary);

  if (flag("--send")) {
    const target = argValue("--target", DEFAULT_TARGET);
    await sendTelegram(target, summary, pngPath);
    console.log(`\nEnviado para Telegram ${target}.`);
  }
} finally {
  await pool.close();
}
