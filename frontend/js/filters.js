// Peças da barra de filtros usadas na lista e no quadro. Cada tela guarda seus filtros num objeto
// e passa `changed` para ser chamado quando algo muda.

import { api } from "./api.js";
import { el, icon } from "./dom.js";

export function selectField(id, label, options, value, onChange) {
  return el(
    "div",
    { class: "field field-compact" },
    el("label", { for: id }, label),
    el(
      "select",
      { class: "input", id, onChange: (event) => onChange(event.target.value) },
      options.map(([optionValue, text]) => el("option", { value: optionValue, selected: optionValue === value }, text)),
    ),
  );
}

/** Botões liga/desliga: cada um adiciona ou tira o valor de `filters[key]`. */
export function chipGroup(label, key, labels, filters, changed) {
  return el(
    "div",
    { class: "chip-group", role: "group", "aria-label": label },
    el("span", { class: "chip-group-label" }, label),
    Object.entries(labels).map(([value, text]) =>
      el(
        "button",
        {
          type: "button",
          class: `chip chip-${key}-${value.toLowerCase()}`,
          "aria-pressed": String(filters[key].includes(value)),
          onClick: (event) => {
            const pressed = !filters[key].includes(value);
            filters[key] = pressed ? [...filters[key], value] : filters[key].filter((v) => v !== value);
            event.currentTarget.setAttribute("aria-pressed", String(pressed));
            changed();
          },
        },
        text,
      ),
    ),
  );
}

/** Campo de busca: espera a pessoa parar de digitar antes de buscar. */
export function searchField(filters, changed) {
  let debounce;
  return el(
    "div",
    { class: "search-field" },
    icon("search"),
    el("input", {
      class: "input search-input",
      type: "search",
      id: "filter-q",
      placeholder: "Buscar por título, descrição ou #número",
      "aria-label": "Buscar chamados",
      value: filters.q,
      maxlength: 100,
      onInput: (event) => {
        clearTimeout(debounce);
        debounce = setTimeout(() => {
          filters.q = event.target.value;
          changed();
        }, 300);
      },
    }),
  );
}

// --- Filtro de responsável ---
// Na URL: "me" = atribuídos a mim, "none" = sem responsável, número = um responsável específico

export function readAssignee(params, user) {
  const assignee = params.get("assignee") ?? "";
  return /^(me|none|\d+)$/.test(assignee) && user.role !== "SOLICITANTE" ? assignee : "";
}

/** Converte o filtro da URL nos parâmetros da API. */
export function assigneeQuery(assignee, user) {
  if (assignee === "me") return { assigned_to_id: user.id };
  if (assignee === "none") return { unassigned: true };
  if (assignee) return { assigned_to_id: assignee };
  return {};
}

export function assigneeOptions(user, people) {
  if (user.role === "SOLICITANTE") return null;
  const options = [["", "Todos"]];
  if (user.role === "TECNICO") options.push(["me", "Atribuídos a mim"]);
  options.push(["none", "Sem responsável"]);
  for (const person of people) options.push([String(person.id), person.name]);
  return options;
}

export function categoryOptions(categories) {
  return [["", "Todas"], ...categories.map((c) => [String(c.id), c.is_active ? c.name : `${c.name} (inativa)`])];
}

/** Categorias e responsáveis para os filtros (a lista de usuários só existe para o admin). */
export function loadFilterOptions(user) {
  const isAdmin = user.role === "ADMIN";
  return Promise.all([
    api.get("/categories", isAdmin ? { include_inactive: true } : {}).catch(() => []),
    isAdmin
      ? api.get("/users", { active: true }).then((users) => users.filter((u) => u.role !== "SOLICITANTE")).catch(() => [])
      : [],
  ]);
}
