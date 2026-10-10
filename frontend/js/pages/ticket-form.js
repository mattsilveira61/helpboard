// Formulário para abrir (sem ?id) ou editar (?id=N) um chamado.
// Na edição, só os campos que o perfil pode alterar ficam habilitados, e só o que mudou é enviado.

import { api } from "../api.js";
import { el, emptyState, icon, setAlert, setFlash } from "../dom.js";
import { PRIORITY_LABELS, SLA_HOURS } from "../labels.js";
import { initPage } from "../layout.js";
import { halt } from "../session.js";
import { backLink, editableFields } from "../tickets.js";

const id = new URLSearchParams(location.search).get("id");
const editing = id !== null;
const back = backLink();
const { user, main } = await initPage(back.pageId, { title: editing ? `Editar chamado #${id}` : "Novo chamado" });

function fail(title, text) {
  main.replaceChildren(
    emptyState(title, text, "alert", el("a", { class: "button button-secondary", href: back.href }, back.label)),
  );
  return halt();
}

if (editing && !/^\d+$/.test(id)) await fail("Chamado não encontrado", "O endereço não aponta para um chamado válido.");

let ticket = null;
let categories;
try {
  [ticket, categories] = await Promise.all([editing ? api.get(`/tickets/${id}`) : null, api.get("/categories")]);
} catch (error) {
  await fail(error.status === 404 ? "Chamado não encontrado" : "Não foi possível carregar o formulário", error.message);
}

const allowed = editing ? editableFields(ticket, user) : ["title", "description", "category_id", "priority"];
if (editing && allowed.length === 0) {
  await fail(
    "Este chamado não pode ser editado",
    ticket.status === "FECHADO"
      ? "Chamado fechado não pode ser alterado. Reabra o chamado primeiro."
      : "Seu perfil não pode alterar nenhum campo deste chamado agora.",
  );
}

// Uma categoria desativada depois da abertura continua aparecendo como a atual do chamado
if (ticket && !categories.some((c) => c.id === ticket.category.id)) {
  categories.push({ ...ticket.category, inactive: true });
}

// --- Campos ---

const fieldErrors = {};

function field(name, label, control, hint) {
  const errorId = `${name}-error`;
  const hintId = `${name}-hint`;
  control.setAttribute("aria-describedby", `${hintId} ${errorId}`);
  if (!allowed.includes(name)) control.disabled = true;
  fieldErrors[name] = el("p", { class: "field-error", id: errorId, hidden: true });
  return el(
    "div",
    { class: "field" },
    el("label", { for: name }, label),
    control,
    el("p", { class: "field-hint", id: hintId, hidden: !hint }, hint ?? ""),
    fieldErrors[name],
  );
}

const title = el("input", { class: "input", id: "title", name: "title", maxlength: 120, value: ticket?.title ?? "", autocomplete: "off" });
const description = el(
  "textarea",
  { class: "input", id: "description", name: "description", rows: 7 },
  ticket?.description ?? "",
);
const category = el(
  "select",
  { class: "input", id: "category_id", name: "category_id" },
  el("option", { value: "", disabled: true, selected: !ticket }, "Selecione…"),
  categories.map((c) =>
    el("option", { value: c.id, selected: c.id === ticket?.category.id, disabled: c.inactive }, c.inactive ? `${c.name} (inativa)` : c.name),
  ),
);
const priority = el(
  "select",
  { class: "input", id: "priority", name: "priority" },
  el("option", { value: "", disabled: true, selected: !ticket }, "Selecione…"),
  Object.entries(PRIORITY_LABELS).map(([value, label]) =>
    el("option", { value, selected: value === ticket?.priority }, `${label} — prazo de ${SLA_HOURS[value]} h`),
  ),
);

// A dica embaixo da categoria mostra a descrição dela ("Internet, Wi-Fi, cabos e VPN")
const categoryHint = () => categories.find((c) => String(c.id) === category.value)?.description;
category.addEventListener("change", () => {
  const hint = form.querySelector("#category_id-hint");
  hint.textContent = categoryHint() ?? "";
  hint.hidden = !hint.textContent;
});
const hints = {
  description: "Conte o que aconteceu, desde quando e o que já foi tentado.",
  priority: editing ? "Mudar a prioridade recalcula o prazo a partir da abertura." : "O prazo de atendimento é calculado pela prioridade.",
};

const alertBox = el("p", { class: "alert", role: "alert", hidden: true });
const submit = el("button", { type: "submit", class: "button button-primary" }, editing ? "Salvar alterações" : "Abrir chamado");
const cancelHref = editing ? `ticket.html?id=${id}` : back.href;

const form = el(
  "form",
  { class: "card form-card", novalidate: true },
  editing && allowed.length < 4 &&
    el("p", { class: "alert alert-info" }, "Alguns campos estão bloqueados porque seu perfil não pode alterá-los neste chamado."),
  field("title", "Título", title),
  field("description", "Descrição", description, hints.description),
  el(
    "div",
    { class: "form-row" },
    field("category_id", "Categoria", category, categoryHint()),
    field("priority", "Prioridade", priority, hints.priority),
  ),
  alertBox,
  el("div", { class: "form-actions" }, el("a", { class: "button button-secondary", href: cancelHref }, "Cancelar"), submit),
);

// --- Validação (as mesmas regras da API, para avisar antes de enviar) ---

function validate(values) {
  const errors = {};
  if (allowed.includes("title")) {
    if (values.title.length < 3) errors.title = "O título precisa ter pelo menos 3 caracteres.";
    else if (values.title.length > 120) errors.title = "O título pode ter no máximo 120 caracteres.";
  }
  if (allowed.includes("description") && !values.description) errors.description = "Descreva o problema.";
  if (allowed.includes("category_id") && !values.category_id) errors.category_id = "Escolha uma categoria.";
  if (allowed.includes("priority") && !values.priority) errors.priority = "Escolha uma prioridade.";
  return errors;
}

function showErrors(errors) {
  for (const [name, node] of Object.entries(fieldErrors)) {
    node.textContent = errors[name] ?? "";
    node.hidden = !errors[name];
    form.elements[name].setAttribute("aria-invalid", String(Boolean(errors[name])));
  }
  const first = Object.keys(fieldErrors).find((name) => errors[name]);
  if (first) form.elements[first].focus();
}

function readValues() {
  return {
    title: title.value.trim(),
    description: description.value.trim(),
    category_id: category.value ? Number(category.value) : null,
    priority: priority.value,
  };
}

/** Na edição, só os campos permitidos que mudaram. */
function changes(values) {
  const current = { title: ticket.title, description: ticket.description, category_id: ticket.category.id, priority: ticket.priority };
  return Object.fromEntries(allowed.filter((name) => values[name] !== current[name]).map((name) => [name, values[name]]));
}

let dirty = false;
form.addEventListener("input", () => (dirty = true));
// Avisa antes de sair com alterações não salvas
window.addEventListener("beforeunload", (event) => {
  if (dirty) event.preventDefault();
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setAlert(alertBox, "");
  const values = readValues();
  const errors = validate(values);
  showErrors(errors);
  if (Object.keys(errors).length > 0) return;

  const body = editing ? changes(values) : values;
  if (editing && Object.keys(body).length === 0) {
    setAlert(alertBox, "Nenhuma alteração para salvar.", "info");
    return;
  }

  submit.disabled = true;
  submit.textContent = "Salvando…";
  try {
    const saved = editing ? await api.patch(`/tickets/${id}`, body) : await api.post("/tickets", body);
    dirty = false;
    setFlash(editing ? "Alterações salvas." : `Chamado #${saved.id} aberto.`);
    location.href = `ticket.html?id=${saved.id}`;
  } catch (error) {
    setAlert(alertBox, error.message);
    submit.disabled = false;
    submit.textContent = editing ? "Salvar alterações" : "Abrir chamado";
  }
});

main.replaceChildren(
  el(
    "div",
    { class: "page-narrow" },
    el("a", { class: "back-link", href: cancelHref }, icon("back"), editing ? `Voltar ao chamado #${id}` : back.label),
    form,
  ),
);
(allowed.includes("title") ? title : form.querySelector(":enabled.input"))?.focus();
