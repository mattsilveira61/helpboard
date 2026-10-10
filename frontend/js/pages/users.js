// Gerenciamento de usuários (só admin): lista com busca e filtros, criar, editar, desativar e reativar.

import { api } from "../api.js";
import { activeBadge, cell, confirmAction, dateCell, loadError, normalize, rowButton, table, toolbar } from "../admin.js";
import { openDialog } from "../dialog.js";
import { el, emptyState, initials, toast } from "../dom.js";
import { ROLE_LABELS } from "../labels.js";
import { initPage } from "../layout.js";

const { user: me, main } = await initPage("users");

const filters = { q: "", role: "", active: "true" };
let users = [];
const results = el("section", { class: "results", "aria-live": "polite" });

const roleOptions = Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }));

function select(label, name, options) {
  return el(
    "label",
    { class: "field field-compact" },
    el("span", {}, label),
    el(
      "select",
      {
        class: "input",
        name,
        onChange: (event) => {
          filters[name] = event.target.value;
          show();
        },
      },
      options.map(({ value, label: text }) => el("option", { value, selected: value === filters[name] }, text)),
    ),
  );
}

function visible() {
  const q = normalize(filters.q.trim());
  return users.filter(
    (u) =>
      (!filters.role || u.role === filters.role) &&
      (!filters.active || String(u.is_active) === filters.active) &&
      (!q || normalize(u.name).includes(q) || normalize(u.email).includes(q)),
  );
}

// --- Formulário (criar e editar usam o mesmo diálogo) ---

function userFields(target) {
  const self = target?.id === me.id;
  return [
    { name: "name", label: "Nome", type: "text", value: target?.name, required: true, maxlength: 100 },
    { name: "email", label: "E-mail", type: "email", value: target?.email, required: true },
    {
      name: "role",
      label: "Perfil",
      type: "select",
      value: target?.role ?? "SOLICITANTE",
      // O admin não pode tirar o próprio perfil de administrador (a API também recusa)
      options: self ? roleOptions.filter((o) => o.value === "ADMIN") : roleOptions,
    },
    {
      name: "password",
      label: target ? "Nova senha" : "Senha",
      type: "password",
      required: !target,
      autocomplete: "new-password",
      hint: target ? "Deixe em branco para manter a senha atual. Mínimo de 8 caracteres." : "Mínimo de 8 caracteres.",
    },
  ];
}

function checkPassword(password, required) {
  if (!password && !required) return;
  if (password.length < 8) throw new Error("A senha precisa ter pelo menos 8 caracteres.");
}

async function createUser() {
  const created = await openDialog({
    title: "Novo usuário",
    fields: userFields(null),
    confirmLabel: "Criar usuário",
    onConfirm: (values) => {
      checkPassword(values.password, true);
      return api.post("/users", { ...values, name: values.name.trim(), email: values.email.trim() });
    },
  });
  if (created) {
    toast(`Usuário ${created.name} criado.`);
    load();
  }
}

async function editUser(target) {
  const saved = await openDialog({
    title: `Editar ${target.name}`,
    fields: userFields(target),
    confirmLabel: "Salvar",
    onConfirm: (values) => {
      checkPassword(values.password, false);
      // Manda só o que mudou
      const changes = {};
      if (values.name.trim() !== target.name) changes.name = values.name.trim();
      if (values.email.trim().toLowerCase() !== target.email.toLowerCase()) changes.email = values.email.trim();
      if (values.role !== target.role) changes.role = values.role;
      if (values.password) changes.password = values.password;
      return Object.keys(changes).length ? api.patch(`/users/${target.id}`, changes) : target;
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
        title: "Desativar usuário",
        text: `${target.name} não vai mais conseguir entrar. Os chamados dele continuam no sistema e você pode reativá-lo depois.`,
        confirmLabel: "Desativar",
        danger: true,
        action: () => api.delete(`/users/${target.id}`),
        success: `${target.name} foi desativado.`,
      })
    : await confirmAction({
        title: "Reativar usuário",
        text: `${target.name} volta a conseguir entrar no sistema.`,
        confirmLabel: "Reativar",
        action: () => api.patch(`/users/${target.id}`, { is_active: true }),
        success: `${target.name} foi reativado.`,
      });
  if (done) load();
}

// --- Tabela ---

function row(u) {
  const self = u.id === me.id;
  return el(
    "tr",
    { class: u.is_active ? null : "row-inactive" },
    cell(
      "Nome",
      el(
        "span",
        { class: "person" },
        el("span", { class: "avatar avatar-sm", "aria-hidden": "true" }, initials(u.name)),
        el("span", {}, u.name, self && el("span", { class: "muted" }, " (você)")),
      ),
    ),
    cell("E-mail", u.email),
    cell("Perfil", el("span", { class: `role-badge role-${u.role.toLowerCase()}` }, ROLE_LABELS[u.role])),
    cell("Situação", activeBadge(u.is_active)),
    cell("Criado em", dateCell(u.created_at)),
    cell(
      "Ações",
      el(
        "div",
        { class: "row-actions" },
        rowButton("Editar", u.name, () => editUser(u), { iconName: "edit" }),
        // A API não deixa o admin desativar a si mesmo
        !self &&
          (u.is_active
            ? rowButton("Desativar", u.name, () => toggleActive(u), { danger: true })
            : rowButton("Reativar", u.name, () => toggleActive(u))),
      ),
    ),
  );
}

function show() {
  const items = visible();
  if (items.length === 0) {
    results.replaceChildren(emptyState("Nenhum usuário encontrado", "Nenhum usuário atende a esses filtros.", "search"));
    return;
  }
  results.replaceChildren(
    el("p", { class: "muted results-count" }, items.length === 1 ? "1 usuário" : `${items.length} usuários`),
    table("Usuários", ["Nome", "E-mail", "Perfil", "Situação", "Criado em", "Ações"], items.map(row)),
  );
}

async function load() {
  results.classList.add("is-loading");
  try {
    users = await api.get("/users");
    show();
  } catch (error) {
    results.replaceChildren(loadError(error.message, load));
  } finally {
    results.classList.remove("is-loading");
  }
}

main.append(
  toolbar({
    searchLabel: "Buscar por nome ou e-mail",
    onSearch: (text) => {
      filters.q = text;
      show();
    },
    controls: [
      select("Perfil", "role", [{ value: "", label: "Todos" }, ...roleOptions]),
      select("Situação", "active", [
        { value: "", label: "Todos" },
        { value: "true", label: "Ativos" },
        { value: "false", label: "Inativos" },
      ]),
    ],
    createLabel: "Novo usuário",
    onCreate: createUser,
  }),
  results,
);
load();
