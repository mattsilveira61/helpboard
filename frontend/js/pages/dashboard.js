// Dashboard de gestão: fila atual, números do período e gráficos simples em CSS (sem biblioteca).
// O admin vê todos os chamados; o técnico, só os atribuídos a ele (a API decide pelo token).

import { api } from "../api.js";
import { el, emptyState } from "../dom.js";
import { PRIORITY_LABELS } from "../labels.js";
import { initPage } from "../layout.js";

const { user, main } = await initPage("dashboard");

const PERIODS = [7, 30, 90];
const KEY = "helpboard.dashboardDays";
let days = PERIODS.includes(Number(sessionStorage.getItem(KEY))) ? Number(sessionStorage.getItem(KEY)) : 30;

const number = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 });
const dayLabel = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", timeZone: "UTC" });

/** Horas médias em texto curto: "5,2 h" ou "1,5 dia". */
function formatHours(hours) {
  if (hours === null || hours === undefined) return "—";
  if (hours < 24) return `${number.format(hours)} h`;
  // Arredonda antes de escolher o plural: 1,96 dia vira "2 dias"
  const value = Math.round((hours / 24) * 10) / 10;
  return `${number.format(value)} ${value >= 2 ? "dias" : "dia"}`;
}

// As datas do período chegam como "2026-10-10" (dia do calendário, sem hora)
const formatDay = (iso) => dayLabel.format(new Date(`${iso}T00:00:00Z`));

/** Link para a lista de chamados já filtrada. */
function listLink(query) {
  const params = new URLSearchParams();
  for (const [key, value] of query) params.append(key, value);
  return `tickets.html?${params}`;
}

// --- Cards de indicadores ---

function stat({ label, value, hint, tone, href }) {
  const body = [
    el("span", { class: "stat-label" }, label),
    el("strong", { class: "stat-value" }, String(value)),
    hint && el("span", { class: "stat-hint" }, hint),
  ];
  const cls = `stat${tone && value > 0 ? ` stat-${tone}` : ""}`;
  return href ? el("a", { class: `${cls} stat-link`, href }, ...body) : el("div", { class: cls }, ...body);
}

function backlogCards(data) {
  const b = data.backlog;
  const unresolved = [["status", "ABERTO"], ["status", "EM_ANDAMENTO"]];
  const mine = data.scope === "MEUS" ? [["assignee", "me"]] : [];
  return el(
    "div",
    { class: "stats" },
    stat({ label: "Abertos", value: b.open, href: listLink([["status", "ABERTO"], ...mine]) }),
    stat({ label: "Em andamento", value: b.in_progress, href: listLink([["status", "EM_ANDAMENTO"], ...mine]) }),
    stat({ label: "Críticos", value: b.critical, tone: "danger", hint: "ainda não resolvidos",
      href: listLink([...unresolved, ["priority", "CRITICA"], ...mine]) }),
    stat({ label: "Atrasados", value: b.overdue, tone: "danger", hint: "passaram do prazo (SLA)" }),
    stat({ label: "Sem responsável", value: b.unassigned, tone: "warning", hint: "disponíveis para assumir",
      href: listLink([["status", "ABERTO"], ["assignee", "none"]]) }),
  );
}

function periodCards(data) {
  return el(
    "div",
    { class: "stats stats-3" },
    stat({ label: "Abertos no período", value: data.created.total }),
    stat({ label: "Resolvidos no período", value: data.resolved.total }),
    stat({ label: "Tempo médio de resolução", value: formatHours(data.resolved.avg_resolution_hours), hint: "da abertura até a solução" }),
  );
}

// --- Gráficos ---

function card(title, ...content) {
  return el("section", { class: "card chart-card" }, el("h2", { class: "card-title" }, title), ...content);
}

function timeline(data) {
  const max = Math.max(1, ...data.timeline.flatMap((d) => [d.created, d.resolved]));
  // Com muitos dias, mostra a data só em alguns rótulos para não encavalar
  const step = Math.ceil(data.timeline.length / 10);
  return card(
    "Abertos × resolvidos por dia",
    el(
      "div",
      { class: "legend" },
      el("span", { class: "legend-item" }, el("i", { class: "swatch swatch-created" }), "Abertos"),
      el("span", { class: "legend-item" }, el("i", { class: "swatch swatch-resolved" }), "Resolvidos"),
    ),
    el(
      "div",
      { class: "timeline", role: "img", "aria-label": `Abertos e resolvidos por dia, de ${formatDay(data.period.start)} a ${formatDay(data.period.end)}` },
      data.timeline.map((d, i) =>
        el(
          "div",
          { class: "timeline-day", title: `${formatDay(d.day)}: ${d.created} abertos, ${d.resolved} resolvidos` },
          el(
            "div",
            { class: "timeline-bars" },
            el("span", { class: "bar bar-created", style: `height: ${(d.created / max) * 100}%` }),
            el("span", { class: "bar bar-resolved", style: `height: ${(d.resolved / max) * 100}%` }),
          ),
          el("span", { class: "timeline-label", "aria-hidden": "true" }, i % step === 0 ? formatDay(d.day) : ""),
        ),
      ),
    ),
  );
}

/** Barras horizontais: [{ label, value, tone }]. */
function bars(title, items, emptyText) {
  const max = Math.max(1, ...items.map((i) => i.value));
  const total = items.reduce((sum, i) => sum + i.value, 0);
  return card(
    title,
    total === 0
      ? el("p", { class: "muted" }, emptyText)
      : el(
          "ul",
          { class: "hbars" },
          items.map((item) =>
            el(
              "li",
              { class: "hbar" },
              el("span", { class: "hbar-label" }, item.label),
              el("span", { class: "hbar-track" },
                el("span", { class: `hbar-fill ${item.tone ?? ""}`, style: `width: ${(item.value / max) * 100}%` })),
              el("span", { class: "hbar-value" }, String(item.value)),
            ),
          ),
        ),
  );
}

function byPriority(data) {
  const items = Object.entries(PRIORITY_LABELS).map(([code, label]) => ({
    label,
    value: data.created.by_priority[code] ?? 0,
    tone: `fill-${code.toLowerCase()}`,
  }));
  return bars("Abertos no período por prioridade", items, "Nenhum chamado aberto no período.");
}

function byCategory(data) {
  const items = [...data.created.by_category]
    .sort((a, b) => b.total - a.total || a.name.localeCompare(b.name))
    .map((c) => ({ label: c.name, value: c.total }));
  return bars("Abertos no período por categoria", items, "Nenhum chamado aberto no período.");
}

function byAssignee(data) {
  const rows = data.by_assignee.map((a) =>
    el(
      "tr",
      {},
      el("td", { "data-label": "Técnico" }, el("a", { href: listLink([["assignee", String(a.id)]]) }, a.name)),
      el("td", { "data-label": "Abertos" }, String(a.open)),
      el("td", { "data-label": "Em andamento" }, String(a.in_progress)),
      el("td", { "data-label": "Resolvidos no período" }, String(a.resolved)),
      el("td", { "data-label": "Tempo médio" }, formatHours(a.avg_resolution_hours)),
    ),
  );
  const headers = ["Técnico", "Abertos", "Em andamento", "Resolvidos no período", "Tempo médio"];
  return card(
    "Por técnico",
    el(
      "div",
      { class: "table-wrap" },
      el(
        "table",
        { class: "table admin-table assignee-table" },
        el("thead", {}, el("tr", {}, headers.map((h) => el("th", { scope: "col" }, h)))),
        el("tbody", {}, rows),
      ),
    ),
  );
}

// --- Montagem ---

const content = el("div", { class: "dashboard", "aria-live": "polite" });

function periodPicker() {
  return el(
    "div",
    { class: "segmented", role: "group", "aria-label": "Período" },
    PERIODS.map((n) =>
      el(
        "button",
        {
          type: "button",
          class: "segmented-button",
          "aria-pressed": String(n === days),
          onClick: (event) => {
            days = n;
            sessionStorage.setItem(KEY, String(n));
            event.currentTarget.parentElement.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === event.currentTarget)));
            load();
          },
        },
        `${n} dias`,
      ),
    ),
  );
}

function render(data) {
  content.replaceChildren(
    el("h2", { class: "section-title" }, data.scope === "MEUS" ? "Sua fila agora" : "Fila agora"),
    backlogCards(data),
    el(
      "h2",
      { class: "section-title" },
      `Período: ${formatDay(data.period.start)} a ${formatDay(data.period.end)}`,
    ),
    periodCards(data),
    timeline(data),
    el("div", { class: "chart-grid" }, byPriority(data), byCategory(data)),
    data.scope === "TODOS" && byAssignee(data),
  );
}

let requestId = 0;

async function load() {
  const id = ++requestId;
  content.classList.add("is-loading");
  const end = new Date();
  const start = new Date(end.getTime() - (days - 1) * 86400000);
  // Dia local no formato da API (AAAA-MM-DD); "sv-SE" já formata assim
  const iso = (d) => d.toLocaleDateString("sv-SE");
  try {
    const data = await api.get("/dashboard", { start: iso(start), end: iso(end) });
    if (id === requestId) render(data);
  } catch (error) {
    if (id !== requestId) return;
    content.replaceChildren(
      emptyState("Não foi possível carregar o dashboard", error.message, "alert",
        el("button", { type: "button", class: "button button-secondary", onClick: load }, "Tentar de novo")),
    );
  } finally {
    if (id === requestId) content.classList.remove("is-loading");
  }
}

main.append(
  el(
    "div",
    { class: "dashboard-header" },
    el(
      "p",
      { class: "muted" },
      user.role === "TECNICO" ? "Números dos chamados atribuídos a você." : "Números de todos os chamados (arquivados não entram).",
    ),
    periodPicker(),
  ),
  content,
);
load();
