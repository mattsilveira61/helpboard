// Respostas prontas (só admin): textos que os técnicos inserem nos comentários.

import { api } from "../api.js";
import { activeBadge, cell, confirmAction, loadError, normalize, rowButton, table, toolbar } from "../admin.js";
import { openDialog } from "../dialog.js";
import { el, emptyState, toast } from "../dom.js";
import { initPage } from "../layout.js";

const { main } = await initPage("canned");

const filters = { q: "", active: "" };
let responses = [];
const results = el("section", { class: "results", "aria-live": "polite" });

function visible() {
  const q = normalize(filters.q.trim());
  return responses.filter(
    (r) =>
      (!filters.active || String(r.is_active) === filters.active) &&
      (!q || normalize(r.title).includes(q) || normalize(r.body).includes(q)),
  );
}

function fields(target) {
  return [
    { name: "title", label: "Título", type: "text", value: target?.title, required: true, maxlength: 80,
      hint: "Aparece no seletor do técnico." },
    { name: "body", label: "Texto", type: "textarea", rows: 5, value: target?.body, required: true, maxlength: 5000 },
  ];
}

async function createResponse() {
  const created = await openDialog({
    title: "Nova resposta pronta",
    fields: fields(null),
    confirmLabel: "Criar resposta",
    onConfirm: (values) => api.post("/canned-responses", { title: values.title.trim(), body: values.body.trim() }),
  });
  if (created) {
    toast(`Resposta "${created.title}" criada.`);
    load();
  }
}

async function editResponse(target) {
  const saved = await openDialog({
    title: `Editar ${target.title}`,
    fields: fields(target),
    confirmLabel: "Salvar",
    onConfirm: (values) => {
      const changes = {};
      if (values.title.trim() !== target.title) changes.title = values.title.trim();
      if (values.body.trim() !== target.body) changes.body = values.body.trim();
      return Object.keys(changes).length ? api.patch(`/canned-responses/${target.id}`, changes) : target;
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
        title: "Desativar resposta",
        text: `"${target.title}" deixa de aparecer para os técnicos.`,
        confirmLabel: "Desativar",
        danger: true,
        action: () => api.delete(`/canned-responses/${target.id}`),
        success: `Resposta "${target.title}" desativada.`,
      })
    : await confirmAction({
        title: "Reativar resposta",
        text: `"${target.title}" volta a aparecer para os técnicos.`,
        confirmLabel: "Reativar",
        action: () => api.patch(`/canned-responses/${target.id}`, { is_active: true }),
        success: `Resposta "${target.title}" reativada.`,
      });
  if (done) load();
}

function row(r) {
  return el(
    "tr",
    { class: r.is_active ? null : "row-inactive" },
    cell("Título", el("strong", {}, r.title)),
    cell("Texto", el("span", { class: "canned-body" }, r.body)),
    cell("Situação", activeBadge(r.is_active, { male: false })),
    cell(
      "Ações",
      el(
        "div",
        { class: "row-actions" },
        rowButton("Editar", r.title, () => editResponse(r), { iconName: "edit" }),
        r.is_active
          ? rowButton("Desativar", r.title, () => toggleActive(r), { danger: true })
          : rowButton("Reativar", r.title, () => toggleActive(r)),
      ),
    ),
  );
}

function show() {
  if (responses.length === 0) {
    results.replaceChildren(
      emptyState("Nenhuma resposta pronta", "Crie textos que os técnicos usam com frequência nos comentários.", "message"),
    );
    return;
  }
  const items = visible();
  if (items.length === 0) {
    results.replaceChildren(emptyState("Nenhuma resposta encontrada", "Nenhuma resposta atende a esses filtros.", "search"));
    return;
  }
  results.replaceChildren(
    el("p", { class: "muted results-count" }, items.length === 1 ? "1 resposta" : `${items.length} respostas`),
    table("Respostas prontas", ["Título", "Texto", "Situação", "Ações"], items.map(row)),
  );
}

async function load() {
  results.classList.add("is-loading");
  try {
    responses = await api.get("/canned-responses", { include_inactive: true });
    show();
  } catch (error) {
    results.replaceChildren(loadError(error.message, load));
  } finally {
    results.classList.remove("is-loading");
  }
}

main.append(
  toolbar({
    searchLabel: "Buscar resposta",
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
    createLabel: "Nova resposta",
    onCreate: createResponse,
  }),
  results,
);
load();
