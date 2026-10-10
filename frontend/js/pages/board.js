// Quadro Kanban: uma coluna por status. O cartão muda de coluna arrastando (mouse) ou pelo menu ⋯
// (teclado e celular). As duas formas chamam a mesma rota de mudança de status da API.
//
// Durante o arraste, cada coluna mostra se aceita o cartão e, se não aceita, o motivo.
// A API continua sendo quem decide: se ela recusar, o cartão volta para a coluna de origem e o erro aparece.

import { api } from "../api.js";
import { el, emptyState, icon, initials, toast } from "../dom.js";
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
import { PRIORITY_LABELS, STATUS_LABELS } from "../labels.js";
import { initPage } from "../layout.js";
import {
  canAssume,
  moveBlocker,
  priorityBadge,
  rememberBack,
  requestStatusChange,
  slaBadge,
  statusActions,
} from "../tickets.js";

const STATUSES = Object.keys(STATUS_LABELS);
// Cartões por coluna; o restante fica a um clique, na lista
const COLUMN_LIMIT = 50;

const { user, main } = await initPage("board");

// --- Filtros <-> URL (o status não é filtro aqui: cada status é uma coluna) ---

function readFilters() {
  const params = new URLSearchParams(location.search);
  return {
    q: params.get("q") ?? "",
    priority: params.getAll("priority").filter((p) => p in PRIORITY_LABELS),
    category_id: /^\d+$/.test(params.get("category_id")) ? params.get("category_id") : "",
    assignee: readAssignee(params, user),
  };
}

const filters = readFilters();

function filterParams() {
  const params = new URLSearchParams();
  if (filters.q.trim()) params.set("q", filters.q.trim());
  for (const value of filters.priority) params.append("priority", value);
  for (const key of ["category_id", "assignee"]) if (filters[key]) params.set(key, filters[key]);
  return params;
}

function writeUrl() {
  const params = filterParams();
  const search = params.toString() ? `?${params}` : "";
  history.replaceState(null, "", `board.html${search}`);
  // O "Voltar" do detalhe volta para o quadro com os mesmos filtros
  rememberBack(`board.html${search}`);
}

/** A mesma busca na lista, só com um status: usado no "Ver todos" das colunas cheias. */
function listHref(status) {
  const params = filterParams();
  params.set("status", status);
  return `tickets.html?${params}`;
}

function apiQuery() {
  const { assignee, ...query } = filters;
  return { ...query, q: filters.q.trim(), ...assigneeQuery(assignee, user) };
}

function hasFilters() {
  return Boolean(filters.q.trim() || filters.priority.length || filters.category_id || filters.assignee);
}

// --- Barra de filtros ---

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
      { class: "filters-row" },
      chipGroup("Prioridade", "priority", PRIORITY_LABELS, filters, changed),
      selectField("filter-category", "Categoria", categoryOptions(categories), filters.category_id, (value) => {
        filters.category_id = value;
        changed();
      }),
      assignee &&
        selectField("filter-assignee", "Responsável", assignee, filters.assignee, (value) => {
          filters.assignee = value;
          changed();
        }),
      el("button", { type: "button", class: "button button-ghost clear-filters", hidden: !hasFilters(), onClick: clearFilters }, "Limpar filtros"),
    ),
  );
}

function clearFilters() {
  Object.assign(filters, { q: "", priority: [], category_id: "", assignee: "" });
  render();
}

// --- Ações do cartão ---

let busy = false;
// Cartão que recebe o foco depois de redesenhar o quadro (quem usa o teclado não perde o lugar)
let focusId = null;

/** Roda uma ação e recarrega o quadro. Se der erro (ou a pessoa cancelar), o recarregamento devolve o cartão ao lugar. */
async function runAction(ticket, action, success) {
  busy = true;
  try {
    if (await action()) toast(success);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    busy = false;
    focusId = ticket.id;
    await load();
  }
}

function moveTicket(ticket, transition) {
  return runAction(ticket, () => requestStatusChange(ticket, transition), `#${ticket.id} movido para ${STATUS_LABELS[transition.to]}.`);
}

function assumeTicket(ticket) {
  return runAction(ticket, async () => {
    await api.post(`/tickets/${ticket.id}/assume`);
    return true;
  }, `Agora você é o responsável pelo #${ticket.id}.`);
}

// Menu ⋯ do cartão: popover nativo (fecha com Esc ou clicando fora) e setas para navegar
let menuCounter = 0;

function cardMenu(ticket, moves) {
  const items = moves.map((transition) =>
    menuItem(
      [transition.label, el("span", { class: "menu-hint" }, icon("arrow"), STATUS_LABELS[transition.to])],
      () => moveTicket(ticket, transition),
    ),
  );
  if (canAssume(ticket, user)) items.unshift(menuItem(["Assumir chamado"], () => assumeTicket(ticket)));
  if (items.length === 0) return null;

  const id = `card-menu-${++menuCounter}`;
  const button = el(
    "button",
    {
      type: "button",
      class: "icon-button card-menu-button",
      popovertarget: id,
      "aria-haspopup": "menu",
      "aria-label": `Ações do chamado #${ticket.id}`,
    },
    icon("more"),
  );
  const menu = el(
    "div",
    {
      class: "menu",
      id,
      popover: "auto",
      role: "menu",
      "aria-label": `Ações do chamado #${ticket.id}`,
      onKeydown: (event) => {
        const buttons = [...menu.querySelectorAll("[role=menuitem]")];
        const index = buttons.indexOf(document.activeElement);
        const next = { ArrowDown: index + 1, ArrowUp: index - 1, Home: 0, End: buttons.length - 1 }[event.key];
        if (next === undefined) return;
        event.preventDefault();
        buttons.at(next % buttons.length).focus();
      },
      // O menu fica na camada de cima da página: abre embaixo do botão, alinhado pela direita
      onBeforetoggle: (event) => {
        if (event.newState !== "open") return;
        const rect = button.getBoundingClientRect();
        menu.style.right = `${Math.max(8, window.innerWidth - rect.right)}px`;
        menu.style.top = `${rect.bottom + 4}px`;
      },
      onToggle: (event) => {
        const open = event.newState === "open";
        button.setAttribute("aria-expanded", String(open));
        if (!open) return;
        // Sem espaço embaixo: abre para cima
        const rect = button.getBoundingClientRect();
        if (rect.bottom + 4 + menu.offsetHeight > window.innerHeight) {
          menu.style.top = `${Math.max(8, rect.top - menu.offsetHeight - 4)}px`;
        }
        menu.querySelector("[role=menuitem]").focus();
      },
    },
    items.map((item) => {
      item.addEventListener("click", () => menu.hidePopover());
      return item;
    }),
  );
  return [button, menu];
}

function menuItem(content, onSelect) {
  return el("button", { type: "button", class: "menu-item", role: "menuitem", tabindex: "-1", onClick: onSelect }, ...content);
}

// Um menu aberto não acompanha a rolagem: fecha
addEventListener("scroll", () => document.querySelector(".menu:popover-open")?.hidePopover(), true);

// --- Arrastar e soltar ---

let dragging = null;

function startDrag(event, ticket, node, moves) {
  if (busy) {
    event.preventDefault();
    return;
  }
  dragging = { ticket, node, moves: new Map(moves.map((t) => [t.to, t])), over: null, dropped: false };
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", `#${ticket.id}`);
  node.classList.add("is-dragging");
  board.classList.add("is-dragging");
  for (const column of board.querySelectorAll(".board-column")) {
    const status = column.dataset.status;
    if (status === ticket.status) continue;
    const transition = dragging.moves.get(status);
    column.classList.add(transition ? "drop-allowed" : "drop-blocked");
    // O aviso aparece sobre a coluna enquanto o cartão é arrastado
    column.querySelector(".drop-hint").textContent = transition ? `Soltar para: ${transition.label}` : moveBlocker(ticket, user, status);
  }
}

function endDrag() {
  if (!dragging) return;
  const { ticket, node, over, dropped } = dragging;
  dragging = null;
  node.classList.remove("is-dragging");
  board.classList.remove("is-dragging");
  for (const column of board.querySelectorAll(".board-column")) {
    column.classList.remove("drop-allowed", "drop-blocked", "drop-over");
  }
  // Soltou numa coluna que não aceita: o navegador devolve o cartão e aqui aparece o motivo
  if (!dropped && over) toast(moveBlocker(ticket, user, over), "error");
}

function dropTarget(column, status) {
  column.addEventListener("dragover", (event) => {
    if (!dragging) return;
    if (dragging.ticket.status === status) {
      dragging.over = null;
      return;
    }
    event.preventDefault();
    const allowed = dragging.moves.has(status);
    event.dataTransfer.dropEffect = allowed ? "move" : "none";
    dragging.over = allowed ? null : status;
    column.classList.add("drop-over");
  });
  column.addEventListener("dragleave", (event) => {
    if (column.contains(event.relatedTarget)) return;
    column.classList.remove("drop-over");
    if (dragging?.over === status) dragging.over = null;
  });
  column.addEventListener("drop", (event) => {
    event.preventDefault();
    const transition = dragging?.moves.get(status);
    if (!transition) return;
    const { ticket, node } = dragging;
    dragging.dropped = true;
    // O cartão já aparece na coluna nova enquanto a API responde (ou enquanto o diálogo está aberto)
    column.querySelector(".board-empty")?.remove();
    column.querySelector(".board-list").prepend(node);
    node.classList.add("is-saving");
    moveTicket(ticket, transition);
  });
}

// --- Cartões e colunas ---

function assigneeTag(ticket) {
  if (!ticket.assigned_to) return el("span", { class: "card-assignee muted" }, "Sem responsável");
  return el(
    "span",
    { class: "card-assignee", title: `Responsável: ${ticket.assigned_to.name}` },
    el("span", { class: "avatar avatar-xs", "aria-hidden": "true" }, initials(ticket.assigned_to.name)),
    ticket.assigned_to.name,
  );
}

function card(ticket) {
  const href = `ticket.html?id=${ticket.id}`;
  const moves = statusActions(ticket, user);
  const critical = ticket.priority === "CRITICA" && !ticket.resolved_at;

  const node = el(
    "li",
    {
      class: `board-card${critical ? " is-critical" : ""}${moves.length ? " is-movable" : ""}`,
      "data-id": ticket.id,
      draggable: moves.length > 0 ? "true" : null,
      // O cartão inteiro abre o detalhe; o link do título é o caminho para teclado e leitores de tela
      onClick: (event) => {
        if (!event.target.closest("a, button, .menu") && !getSelection().toString()) location.href = href;
      },
      onDragstart: (event) => startDrag(event, ticket, node, moves),
      onDragend: endDrag,
    },
    el(
      "div",
      { class: "card-top" },
      el("span", { class: "ticket-number" }, `#${ticket.id}`),
      priorityBadge(ticket.priority),
      cardMenu(ticket, moves),
    ),
    el("a", { class: "board-card-title ticket-link", href, draggable: "false" }, ticket.title),
    el("p", { class: "card-category" }, ticket.category.name),
    el("div", { class: "card-bottom" }, assigneeTag(ticket), slaBadge(ticket, { short: true })),
  );
  return node;
}

function column(status, page) {
  const titleId = `column-${status.toLowerCase()}`;
  const node = el(
    "section",
    { class: `board-column column-${status.toLowerCase()}`, "data-status": status, "aria-labelledby": titleId },
    el(
      "header",
      { class: "board-column-header" },
      el("h2", { id: titleId }, STATUS_LABELS[status]),
      el("span", { class: "board-count" }, String(page.total), el("span", { class: "visually-hidden" }, " chamados")),
    ),
    el("p", { class: "drop-hint", "aria-hidden": "true" }),
    el("ol", { class: "board-list" }, page.items.map(card)),
    page.items.length === 0 && el("p", { class: "board-empty" }, hasFilters() ? "Nenhum chamado com esses filtros" : "Nenhum chamado"),
    page.total > page.items.length &&
      el("a", { class: "board-more", href: listHref(status) }, `Ver todos os ${page.total} na lista`, icon("arrow")),
  );
  dropTarget(node, status);
  return node;
}

// --- Carregamento ---

const summary = el("p", { class: "board-summary muted", "aria-live": "polite" });
const board = el("div", { class: "board", "aria-busy": "true" });
let requestId = 0;

function changed() {
  main.querySelector(".clear-filters").hidden = !hasFilters();
  load();
}

async function load() {
  writeUrl();
  const id = ++requestId;
  board.setAttribute("aria-busy", "true");
  board.classList.add("is-loading");
  try {
    // Uma busca por coluna: cada uma traz o total do status, mesmo que só parte dos cartões caiba
    const query = apiQuery();
    const pages = await Promise.all(
      STATUSES.map((status) => api.get("/tickets", { ...query, status, page_size: COLUMN_LIMIT })),
    );
    if (id !== requestId) return; // chegou depois de uma busca mais nova
    const total = pages.reduce((sum, page) => sum + page.total, 0);
    summary.textContent = `${total} ${total === 1 ? "chamado" : "chamados"}${hasFilters() ? " com esses filtros" : ""}`;
    board.replaceChildren(...STATUSES.map((status, i) => column(status, pages[i])));
    if (focusId !== null) {
      board.querySelector(`.board-card[data-id="${focusId}"] .ticket-link`)?.focus({ preventScroll: true });
      focusId = null;
    }
  } catch (error) {
    if (id !== requestId) return;
    summary.textContent = "";
    board.replaceChildren(
      emptyState("Não foi possível carregar o quadro", error.message, "alert",
        el("button", { type: "button", class: "button button-secondary", onClick: load }, "Tentar de novo")),
    );
  } finally {
    if (id === requestId) {
      board.setAttribute("aria-busy", "false");
      board.classList.remove("is-loading");
    }
  }
}

function render() {
  main.replaceChildren(
    filterBar(categories, people),
    el(
      "div",
      { class: "board-toolbar" },
      summary,
      el("p", { class: "board-tip muted" }, "Arraste os cartões entre as colunas ou use o menu ", icon("more"), " de cada cartão."),
    ),
    board,
  );
  load();
}

const [categories, people] = await loadFilterOptions(user);
render();
