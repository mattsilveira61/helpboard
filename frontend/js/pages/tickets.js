// Lista de chamados com busca, filtros e paginação. Os filtros ficam na URL: recarregar a página,
// voltar do detalhe ou compartilhar o link mostra a mesma lista.

import { api } from "../api.js";
import { el, emptyState, icon } from "../dom.js";
import {
  assigneeOptions,
  assigneeQuery,
  categoryOptions,
  chipGroup,
  loadFilterOptions,
  readAssignee,
  searchField,
  selectField,
} from "../filters.js";
import { formatDate, formatDateTime } from "../format.js";
import { PRIORITY_LABELS, STATUS_LABELS } from "../labels.js";
import { initPage } from "../layout.js";
import { priorityBadge, rememberBack, slaBadge, statusBadge } from "../tickets.js";

const PAGE_SIZES = [10, 20, 50];
const DATE = /^\d{4}-\d{2}-\d{2}$/;

const { user, main } = await initPage("tickets");
const isAdmin = user.role === "ADMIN";

// --- Filtros <-> URL ---

function readFilters() {
  const params = new URLSearchParams(location.search);
  const pageSize = Number(params.get("page_size"));
  return {
    q: params.get("q") ?? "",
    status: params.getAll("status").filter((s) => s in STATUS_LABELS),
    priority: params.getAll("priority").filter((p) => p in PRIORITY_LABELS),
    category_id: /^\d+$/.test(params.get("category_id")) ? params.get("category_id") : "",
    assignee: readAssignee(params, user),
    created_from: DATE.test(params.get("created_from")) ? params.get("created_from") : "",
    created_to: DATE.test(params.get("created_to")) ? params.get("created_to") : "",
    include_archived: isAdmin && params.get("include_archived") === "true",
    page: Math.max(1, Number.parseInt(params.get("page"), 10) || 1),
    page_size: PAGE_SIZES.includes(pageSize) ? pageSize : 20,
  };
}

const filters = readFilters();

function writeUrl() {
  const params = new URLSearchParams();
  if (filters.q.trim()) params.set("q", filters.q.trim());
  for (const key of ["status", "priority"]) for (const value of filters[key]) params.append(key, value);
  for (const key of ["category_id", "assignee", "created_from", "created_to"]) {
    if (filters[key]) params.set(key, filters[key]);
  }
  if (filters.include_archived) params.set("include_archived", "true");
  if (filters.page > 1) params.set("page", filters.page);
  if (filters.page_size !== 20) params.set("page_size", filters.page_size);

  const search = params.toString() ? `?${params}` : "";
  history.replaceState(null, "", `tickets.html${search}`);
  // O detalhe usa isto no "Voltar" para cair na mesma página da lista
  rememberBack(`tickets.html${search}`);
}

function apiQuery() {
  const { assignee, ...query } = filters;
  query.q = filters.q.trim();
  if (!query.include_archived) delete query.include_archived;
  return { ...query, ...assigneeQuery(assignee, user) };
}

function hasFilters() {
  return Boolean(
    filters.q.trim() || filters.status.length || filters.priority.length || filters.category_id ||
      filters.assignee || filters.created_from || filters.created_to || filters.include_archived,
  );
}

// --- Barra de filtros ---

function dateInput(id, label, key) {
  return el(
    "div",
    { class: "field field-compact" },
    el("label", { for: id }, label),
    el("input", {
      class: "input",
      type: "date",
      id,
      value: filters[key],
      onChange: (event) => {
        filters[key] = event.target.value;
        changed();
      },
    }),
  );
}

function filterBar(categories, people) {
  const assignee = assigneeOptions(user, people);

  return el(
    "form",
    { class: "filters", role: "search", onSubmit: (event) => event.preventDefault() },
    el(
      "div",
      { class: "filters-top" },
      searchField(filters, changed),
      el("a", { class: "button button-primary", href: "ticket-form.html" }, icon("plus"), "Novo chamado"),
    ),
    el(
      "div",
      { class: "filters-chips" },
      chipGroup("Status", "status", STATUS_LABELS, filters, changed),
      chipGroup("Prioridade", "priority", PRIORITY_LABELS, filters, changed),
    ),
    el(
      "div",
      { class: "filters-row" },
      selectField("filter-category", "Categoria", categoryOptions(categories), filters.category_id, (value) => {
        filters.category_id = value;
        changed();
      }),
      assignee &&
        selectField("filter-assignee", "Responsável", assignee, filters.assignee, (value) => {
          filters.assignee = value;
          changed();
        }),
      dateInput("filter-from", "Aberto de", "created_from"),
      dateInput("filter-to", "até", "created_to"),
      isAdmin &&
        el(
          "label",
          { class: "checkbox" },
          el("input", {
            type: "checkbox",
            id: "filter-archived",
            checked: filters.include_archived,
            onChange: (event) => {
              filters.include_archived = event.target.checked;
              changed();
            },
          }),
          "Incluir arquivados",
        ),
      el("button", { type: "button", class: "button button-ghost clear-filters", hidden: !hasFilters(), onClick: clearFilters }, "Limpar filtros"),
    ),
  );
}

function clearFilters() {
  Object.assign(filters, {
    q: "", status: [], priority: [], category_id: "", assignee: "",
    created_from: "", created_to: "", include_archived: false, page: 1,
  });
  render();
}

// --- Tabela ---

function cell(label, ...content) {
  return el("td", { "data-label": label }, ...content);
}

function row(ticket) {
  const href = `ticket.html?id=${ticket.id}`;
  return el(
    "tr",
    {
      class: ticket.priority === "CRITICA" && !ticket.resolved_at ? "row-critical" : null,
      // A linha inteira abre o detalhe; o link no título continua sendo o caminho para teclado e leitores de tela
      onClick: (event) => {
        if (!event.target.closest("a") && !getSelection().toString()) location.href = href;
      },
    },
    cell("Nº", el("span", { class: "ticket-number" }, `#${ticket.id}`)),
    cell(
      "Título",
      el("a", { class: "ticket-link", href }, ticket.title),
      ticket.is_archived && el("span", { class: "badge badge-archived" }, "Arquivado"),
    ),
    cell("Status", statusBadge(ticket.status)),
    cell("Prioridade", priorityBadge(ticket.priority)),
    cell("Categoria", ticket.category.name),
    cell("Responsável", ticket.assigned_to?.name ?? el("span", { class: "muted" }, "Sem responsável")),
    user.role !== "SOLICITANTE" && cell("Solicitante", ticket.requester.name),
    cell("Prazo", slaBadge(ticket, { short: true })),
    cell("Aberto em", el("time", { datetime: ticket.created_at, title: formatDateTime(ticket.created_at) }, formatDate(ticket.created_at))),
  );
}

function table(items) {
  const headers = ["Nº", "Título", "Status", "Prioridade", "Categoria", "Responsável"];
  if (user.role !== "SOLICITANTE") headers.push("Solicitante");
  headers.push("Prazo", "Aberto em");
  return el(
    "div",
    { class: "table-wrap" },
    el(
      "table",
      { class: "table ticket-table" },
      el("caption", { class: "visually-hidden" }, "Chamados"),
      el("thead", {}, el("tr", {}, headers.map((h) => el("th", { scope: "col" }, h)))),
      el("tbody", {}, items.map(row)),
    ),
  );
}

// Números das páginas com reticências: 1 … 4 5 6 … 12
function pageNumbers(current, total) {
  const pages = new Set([1, total, current - 1, current, current + 1]);
  const sorted = [...pages].filter((p) => p >= 1 && p <= total).sort((a, b) => a - b);
  return sorted.flatMap((p, i) => (i > 0 && p - sorted[i - 1] > 1 ? ["…", p] : [p]));
}

function goToPage(page) {
  filters.page = page;
  load();
  main.querySelector(".results")?.scrollIntoView({ block: "start" });
}

function pagination(data) {
  const first = (data.page - 1) * data.page_size + 1;
  const last = Math.min(data.page * data.page_size, data.total);
  return el(
    "div",
    { class: "pagination-bar" },
    el("p", { class: "muted" }, `Mostrando ${first}–${last} de ${data.total}`),
    el(
      "div",
      { class: "pagination-controls" },
      selectField("page-size", "Por página", PAGE_SIZES.map((n) => [String(n), String(n)]), String(filters.page_size), (value) => {
        filters.page_size = Number(value);
        filters.page = 1;
        load();
      }),
      data.pages > 1 &&
        el(
          "nav",
          { class: "pagination", "aria-label": "Páginas" },
          el(
            "button",
            { type: "button", class: "icon-button", "aria-label": "Página anterior", disabled: data.page <= 1, onClick: () => goToPage(data.page - 1) },
            icon("prev"),
          ),
          pageNumbers(data.page, data.pages).map((p) =>
            p === "…"
              ? el("span", { class: "pagination-gap" }, "…")
              : el(
                  "button",
                  {
                    type: "button",
                    class: "page-button",
                    "aria-current": p === data.page ? "page" : null,
                    "aria-label": `Página ${p}`,
                    onClick: () => goToPage(p),
                  },
                  String(p),
                ),
          ),
          el(
            "button",
            { type: "button", class: "icon-button", "aria-label": "Próxima página", disabled: data.page >= data.pages, onClick: () => goToPage(data.page + 1) },
            icon("next"),
          ),
        ),
    ),
  );
}

// --- Carregamento ---

const results = el("section", { class: "results", "aria-live": "polite", "aria-busy": "true" });
let requestId = 0;

function changed() {
  filters.page = 1;
  main.querySelector(".clear-filters").hidden = !hasFilters();
  load();
}

async function load() {
  writeUrl();
  const id = ++requestId;
  results.setAttribute("aria-busy", "true");
  results.classList.add("is-loading");
  try {
    const data = await api.get("/tickets", apiQuery());
    if (id !== requestId) return; // chegou depois de uma busca mais nova
    if (data.pages > 0 && filters.page > data.pages) {
      // A página pedida não existe mais (ex.: link antigo): vai para a última
      filters.page = data.pages;
      return load();
    }
    showResults(data);
  } catch (error) {
    if (id !== requestId) return;
    results.replaceChildren(
      emptyState("Não foi possível carregar os chamados", error.message, "alert",
        el("button", { type: "button", class: "button button-secondary", onClick: load }, "Tentar de novo")),
    );
  } finally {
    if (id === requestId) {
      results.setAttribute("aria-busy", "false");
      results.classList.remove("is-loading");
    }
  }
}

function showResults(data) {
  if (data.total === 0) {
    results.replaceChildren(
      hasFilters()
        ? emptyState("Nenhum chamado encontrado", "Nenhum chamado atende a esses filtros.", "search",
            el("button", { type: "button", class: "button button-secondary", onClick: clearFilters }, "Limpar filtros"))
        : emptyState("Nenhum chamado por aqui", "Quando um chamado for aberto, ele aparece nesta lista.", "inbox",
            el("a", { class: "button button-primary", href: "ticket-form.html" }, icon("plus"), "Abrir chamado")),
    );
    return;
  }
  results.replaceChildren(table(data.items), pagination(data));
}

function render() {
  main.replaceChildren(filterBar(categories, people), results);
  load();
}

const [categories, people] = await loadFilterOptions(user);
render();
