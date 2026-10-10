// Gerenciamento de categorias (só admin): lista com busca, criar, editar, desativar e reativar.

import { api } from "../api.js";
import { activeBadge, cell, confirmAction, dateCell, loadError, normalize, rowButton, table, toolbar } from "../admin.js";
import { openDialog } from "../dialog.js";
import { el, emptyState, toast } from "../dom.js";
import { initPage } from "../layout.js";

const { main } = await initPage("categories");

const filters = { q: "", active: "" };
let categories = [];
const results = el("section", { class: "results", "aria-live": "polite" });

function visible() {
  const q = normalize(filters.q.trim());
  return categories.filter(
    (c) =>
      (!filters.active || String(c.is_active) === filters.active) &&
      (!q || normalize(c.name).includes(q) || normalize(c.description).includes(q)),
  );
}

function categoryFields(target) {
  return [
    { name: "name", label: "Nome", type: "text", value: target?.name, required: true, maxlength: 60 },
    {
      name: "description",
      label: "Descrição (opcional)",
      type: "textarea",
      rows: 3,
      value: target?.description,
      maxlength: 500,
      hint: "Ajuda o solicitante a escolher a categoria certa.",
    },
  ];
}

async function createCategory() {
  const created = await openDialog({
    title: "Nova categoria",
    fields: categoryFields(null),
    confirmLabel: "Criar categoria",
    onConfirm: (values) =>
      api.post("/categories", { name: values.name.trim(), description: values.description.trim() || null }),
  });
  if (created) {
    toast(`Categoria ${created.name} criada.`);
    load();
  }
}

async function editCategory(target) {
  const saved = await openDialog({
    title: `Editar ${target.name}`,
    fields: categoryFields(target),
    confirmLabel: "Salvar",
    onConfirm: (values) => {
      const changes = {};
      // Para a API, null significa "não mexer"; "" apaga a descrição
      const description = values.description.trim();
      if (values.name.trim() !== target.name) changes.name = values.name.trim();
      if (description !== (target.description ?? "")) changes.description = description;
      return Object.keys(changes).length ? api.patch(`/categories/${target.id}`, changes) : target;
    },
  });
  if (saved) {
    toast("Alterações salvas.");
    load();
  }
}

async function toggleActive(target) {
  const done = target.is_active
    ? await confirmAction({
        title: "Desativar categoria",
        text: `"${target.name}" deixa de aparecer no formulário de chamados. Os chamados antigos continuam com ela.`,
        confirmLabel: "Desativar",
        danger: true,
        action: () => api.delete(`/categories/${target.id}`),
        success: `Categoria ${target.name} desativada.`,
      })
    : await confirmAction({
        title: "Reativar categoria",
        text: `"${target.name}" volta a aparecer no formulário de chamados.`,
        confirmLabel: "Reativar",
        action: () => api.patch(`/categories/${target.id}`, { is_active: true }),
        success: `Categoria ${target.name} reativada.`,
      });
  if (done) load();
}

function row(c) {
  return el(
    "tr",
    { class: c.is_active ? null : "row-inactive" },
    cell("Nome", el("strong", {}, c.name)),
    cell("Descrição", c.description || el("span", { class: "muted" }, "Sem descrição")),
    cell("Situação", activeBadge(c.is_active, { male: false })),
    cell("Criada em", dateCell(c.created_at)),
    cell(
      "Ações",
      el(
        "div",
        { class: "row-actions" },
        rowButton("Editar", c.name, () => editCategory(c), { iconName: "edit" }),
        c.is_active
          ? rowButton("Desativar", c.name, () => toggleActive(c), { danger: true })
          : rowButton("Reativar", c.name, () => toggleActive(c)),
      ),
    ),
  );
}

function show() {
  const items = visible();
  if (items.length === 0) {
    results.replaceChildren(emptyState("Nenhuma categoria encontrada", "Nenhuma categoria atende a esses filtros.", "search"));
    return;
  }
  results.replaceChildren(
    el("p", { class: "muted results-count" }, items.length === 1 ? "1 categoria" : `${items.length} categorias`),
    table("Categorias", ["Nome", "Descrição", "Situação", "Criada em", "Ações"], items.map(row)),
  );
}

async function load() {
  results.classList.add("is-loading");
  try {
    categories = await api.get("/categories", { include_inactive: true });
    show();
  } catch (error) {
    results.replaceChildren(loadError(error.message, load));
  } finally {
    results.classList.remove("is-loading");
  }
}

main.append(
  toolbar({
    searchLabel: "Buscar categoria",
    onSearch: (text) => {
      filters.q = text;
      show();
    },
    controls: [
      el(
        "label",
        { class: "field field-compact" },
        el("span", {}, "Situação"),
        el(
          "select",
          {
            class: "input",
            name: "active",
            onChange: (event) => {
              filters.active = event.target.value;
              show();
            },
          },
          el("option", { value: "" }, "Todas"),
          el("option", { value: "true" }, "Ativas"),
          el("option", { value: "false" }, "Inativas"),
        ),
      ),
    ],
    createLabel: "Nova categoria",
    onCreate: createCategory,
  }),
  results,
);
load();
