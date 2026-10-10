// Peças comuns às telas de administração (usuários e categorias): barra de busca, tabela e ações por linha.

import { el, emptyState, icon, toast } from "./dom.js";
import { openDialog } from "./dialog.js";
import { formatDate, formatDateTime } from "./format.js";

/** Tira acentos e caixa para a busca: "Técnica" casa com "tecnica". */
export function normalize(text) {
  return (text ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export function activeBadge(isActive, { male = true } = {}) {
  return isActive
    ? el("span", { class: "badge badge-active" }, male ? "Ativo" : "Ativa")
    : el("span", { class: "badge badge-inactive" }, male ? "Inativo" : "Inativa");
}

export function dateCell(value) {
  return el("time", { datetime: value, title: formatDateTime(value) }, formatDate(value));
}

export function cell(label, ...content) {
  return el("td", { "data-label": label }, ...content);
}

/** Botão pequeno de ação na linha da tabela. `label` vira texto visível; `name` dá contexto ao leitor de tela. */
export function rowButton(label, name, onClick, { danger = false, iconName } = {}) {
  return el(
    "button",
    {
      type: "button",
      class: `button button-small ${danger ? "button-ghost-danger" : "button-ghost"}`,
      "aria-label": `${label}: ${name}`,
      onClick,
    },
    iconName && icon(iconName),
    label,
  );
}

/**
 * Barra superior: busca, controles extras (filtros) e o botão de criar.
 * `onSearch` recebe o texto a cada tecla.
 */
export function toolbar({ searchLabel, onSearch, controls = [], createLabel, onCreate }) {
  return el(
    "div",
    { class: "admin-toolbar", role: "search" },
    el(
      "label",
      { class: "search-field" },
      icon("search"),
      el("span", { class: "visually-hidden" }, searchLabel),
      el("input", {
        class: "input search-input",
        type: "search",
        placeholder: searchLabel,
        onInput: (event) => onSearch(event.target.value),
      }),
    ),
    controls,
    el("button", { type: "button", class: "button button-primary", onClick: onCreate }, icon("plus"), createLabel),
  );
}

/** Tabela simples com cabeçalho; vira cartões no celular (classe admin-table). */
export function table(caption, headers, rows) {
  return el(
    "div",
    { class: "table-wrap" },
    el(
      "table",
      { class: "table admin-table" },
      el("caption", { class: "visually-hidden" }, caption),
      el("thead", {}, el("tr", {}, headers.map((h) => el("th", { scope: "col" }, h)))),
      el("tbody", {}, rows),
    ),
  );
}

/** Pede confirmação e roda a ação; mostra o toast de sucesso. Devolve true se a ação aconteceu. */
export async function confirmAction({ title, text, confirmLabel, danger, action, success }) {
  const done = await openDialog({ title, text, confirmLabel, danger, onConfirm: async () => (await action(), true) });
  if (done) toast(success);
  return Boolean(done);
}

export function loadError(message, retry) {
  return emptyState(
    "Não foi possível carregar",
    message,
    "alert",
    el("button", { type: "button", class: "button button-secondary", onClick: retry }, "Tentar de novo"),
  );
}
