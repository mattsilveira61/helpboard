// Detalhe do chamado: dados, ações conforme o perfil, comentários e histórico.

import { api } from "../api.js";
import { AUTO_CLOSE_DAYS } from "../config.js";
import { openDialog } from "../dialog.js";
import { el, emptyState, icon, initials, setAlert, toast } from "../dom.js";
import { formatDateTime, formatRelative } from "../format.js";
import { PRIORITY_LABELS, STATUS_LABELS } from "../labels.js";
import { initPage } from "../layout.js";
import { halt } from "../session.js";
import {
  backLink,
  canArchive,
  canAssign,
  canAssume,
  commentBlocker,
  editableFields,
  priorityBadge,
  requestStatusChange,
  slaBadge,
  statusActions,
  statusBadge,
} from "../tickets.js";

const id = new URLSearchParams(location.search).get("id");
// O menu marca a tela de onde a pessoa veio (lista ou quadro)
const back = backLink();
const { user, main } = await initPage(back.pageId, { title: `Chamado #${id}` });

function fail(title, text) {
  main.replaceChildren(
    emptyState(title, text, "alert", el("a", { class: "button button-secondary", href: back.href }, back.label)),
  );
  return halt();
}

if (!/^\d+$/.test(id ?? "")) await fail("Chamado não encontrado", "O endereço não aponta para um chamado válido.");

let ticket;
let comments;
let historyItems;
try {
  [ticket, comments, historyItems] = await Promise.all([
    api.get(`/tickets/${id}`),
    api.get(`/tickets/${id}/comments`),
    api.get(`/tickets/${id}/history`),
  ]);
} catch (error) {
  await fail(error.status === 404 ? "Chamado não encontrado" : "Não foi possível carregar o chamado", error.message);
}

// Responsáveis possíveis (só o admin atribui; a lista de usuários é exclusiva dele)
let assignees = null;
async function loadAssignees() {
  assignees ??= (await api.get("/users", { active: true })).filter((u) => u.role !== "SOLICITANTE");
  return assignees;
}

async function refresh() {
  [ticket, comments, historyItems] = await Promise.all([
    api.get(`/tickets/${id}`),
    api.get(`/tickets/${id}/comments`),
    api.get(`/tickets/${id}/history`),
  ]);
  render();
}

/** Roda uma ação na API; em caso de sucesso recarrega a tela e mostra o aviso. */
async function run(action, success) {
  try {
    await action();
    await refresh();
    toast(success);
  } catch (error) {
    toast(error.message, "error");
    // A regra pode ter mudado por outra pessoa: recarrega para mostrar o estado atual
    await refresh().catch(() => {});
  }
}

// --- Ações ---

async function changeStatus(transition) {
  const success = `Status alterado para ${STATUS_LABELS[transition.to]}.`;
  // Com diálogo, os erros aparecem dentro dele; sem diálogo, `run` mostra o erro e recarrega
  if (transition.needs) {
    if (await requestStatusChange(ticket, transition)) await refresh().then(() => toast(success));
    return;
  }
  await run(() => requestStatusChange(ticket, transition), success);
}

async function assign() {
  let people;
  try {
    people = await loadAssignees();
  } catch (error) {
    toast(error.message, "error");
    return;
  }
  const options = people.map((p) => ({ value: String(p.id), label: p.role === "ADMIN" ? `${p.name} (admin)` : p.name }));
  // Sem responsável só é permitido com o chamado em ABERTO
  if (ticket.status === "ABERTO") options.unshift({ value: "", label: "Sem responsável" });

  const saved = await openDialog({
    title: ticket.assigned_to ? "Trocar responsável" : "Atribuir responsável",
    fields: [{ name: "assignee", label: "Responsável", type: "select", options, value: String(ticket.assigned_to?.id ?? "") }],
    confirmLabel: "Salvar",
    onConfirm: async ({ assignee }) => {
      await api.put(`/tickets/${id}/assignee`, { assigned_to_id: assignee ? Number(assignee) : null });
      return true;
    },
  });
  if (saved) await refresh().then(() => toast("Responsável atualizado."));
}

async function archive() {
  const saved = await openDialog({
    title: `Arquivar o chamado #${id}?`,
    text: "Ele some das listas e não pode mais ser alterado. O histórico continua guardado.",
    confirmLabel: "Arquivar",
    danger: true,
    onConfirm: async () => {
      await api.delete(`/tickets/${id}`);
      return true;
    },
  });
  if (saved) await refresh().then(() => toast("Chamado arquivado."));
}

function actionButton(label, onClick, { primary = false, iconName = null } = {}) {
  return el(
    "button",
    {
      type: "button",
      class: `button ${primary ? "button-primary" : "button-secondary"}`,
      onClick: async (event) => {
        // Evita clique duplo enquanto a ação está em andamento
        const button = event.currentTarget;
        button.disabled = true;
        try {
          await onClick();
        } catch (error) {
          toast(error.message, "error");
        } finally {
          button.disabled = false;
        }
      },
    },
    iconName && icon(iconName),
    label,
  );
}

function actions() {
  const buttons = [];
  if (canAssume(ticket, user)) {
    buttons.push(actionButton("Assumir chamado", () => run(() => api.post(`/tickets/${id}/assume`), "Agora você é o responsável."), { primary: true, iconName: "assign" }));
  }
  for (const transition of statusActions(ticket, user)) {
    buttons.push(actionButton(transition.label, () => changeStatus(transition), { primary: transition.primary }));
  }
  if (canAssign(ticket, user)) {
    buttons.push(actionButton(ticket.assigned_to ? "Trocar responsável" : "Atribuir", assign, { iconName: "assign" }));
  }
  if (editableFields(ticket, user).length > 0) {
    buttons.push(el("a", { class: "button button-secondary", href: `ticket-form.html?id=${id}` }, icon("edit"), "Editar"));
  }
  if (canArchive(ticket, user)) {
    buttons.push(actionButton("Arquivar", archive, { iconName: "archive" }));
  }
  if (buttons.length === 0) return null;
  // O botão principal vem primeiro
  buttons.sort((a, b) => b.classList.contains("button-primary") - a.classList.contains("button-primary"));
  return el("div", { class: "ticket-actions" }, buttons);
}

/** Próximo passo esperado, em linguagem simples. */
function nextStep() {
  if (ticket.is_archived) return "Este chamado está arquivado e não pode mais ser alterado.";
  const mine = ticket.requester.id === user.id;
  switch (ticket.status) {
    case "ABERTO":
      return ticket.assigned_to
        ? `${ticket.assigned_to.name} vai iniciar o atendimento.`
        : "Aguardando um técnico assumir o chamado.";
    case "EM_ANDAMENTO":
      return `${ticket.assigned_to?.name ?? "O técnico"} está trabalhando no chamado.`;
    case "RESOLVIDO":
      return mine
        ? `O técnico registrou uma solução. Confira e aceite para fechar, ou recuse se o problema continua. ` +
            `Sem resposta em ${AUTO_CLOSE_DAYS} dias, o chamado é fechado automaticamente.`
        : `Aguardando ${ticket.requester.name} aceitar ou recusar a solução ` +
            `(fecha sozinho em ${AUTO_CLOSE_DAYS} dias sem resposta).`;
    case "FECHADO":
      return mine ? "Chamado encerrado. Se o problema voltar, você pode reabri-lo." : "Chamado encerrado.";
  }
  return null;
}

// --- Blocos da tela ---

function header() {
  return el(
    "header",
    { class: "ticket-header" },
    el("a", { class: "back-link", href: back.href }, icon("back"), back.label),
    el(
      "div",
      { class: "ticket-heading" },
      el("span", { class: "ticket-number" }, `#${ticket.id}`),
      el("h2", { class: "ticket-title" }, ticket.title),
    ),
    el(
      "div",
      { class: "ticket-badges" },
      statusBadge(ticket.status),
      priorityBadge(ticket.priority),
      slaBadge(ticket),
      ticket.is_archived && el("span", { class: "badge badge-archived" }, "Arquivado"),
    ),
    el("p", { class: "next-step" }, nextStep()),
    actions(),
  );
}

function descriptionCard() {
  return el(
    "section",
    { class: "card", "aria-labelledby": "description-title" },
    el("h3", { class: "card-title", id: "description-title" }, "Descrição"),
    el("p", { class: "prose" }, ticket.description),
    ticket.solution &&
      el(
        "div",
        { class: "solution" },
        el("h3", { class: "card-title" }, "Solução"),
        el("p", { class: "prose" }, ticket.solution),
      ),
  );
}

// --- Nota de satisfação ---

const RATING_LABELS = ["", "Muito insatisfeito", "Insatisfeito", "Regular", "Satisfeito", "Muito satisfeito"];

function stars(rating) {
  return el("span", { class: "stars", "aria-label": `${rating} de 5 estrelas` }, "★".repeat(rating) + "☆".repeat(5 - rating));
}

function ratingForm() {
  let chosen = 0;
  const alertBox = el("p", { class: "alert", role: "alert", hidden: true });
  const comment = el("textarea", { class: "input", id: "rating-comment", rows: 2, maxlength: 500, placeholder: "Comentário (opcional)" });
  const submit = el("button", { type: "submit", class: "button button-primary", disabled: true }, "Enviar avaliação");
  const hint = el("span", { class: "muted" }, "Escolha de 1 a 5 estrelas");
  const buttons = [1, 2, 3, 4, 5].map((n) =>
    el("button", {
      type: "button",
      class: "star-button",
      "aria-label": `${n} – ${RATING_LABELS[n]}`,
      "aria-pressed": "false",
      onClick: () => {
        chosen = n;
        buttons.forEach((b, i) => {
          b.textContent = i < n ? "★" : "☆";
          b.setAttribute("aria-pressed", String(i < n));
        });
        hint.textContent = RATING_LABELS[n];
        submit.disabled = false;
      },
    }, "☆"),
  );

  return el(
    "form",
    {
      class: "rating-form",
      onSubmit: async (event) => {
        event.preventDefault();
        setAlert(alertBox, "");
        submit.disabled = true;
        try {
          await api.post(`/tickets/${id}/rating`, { rating: chosen, comment: comment.value.trim() || null });
          await refresh();
          toast("Obrigado pela avaliação!");
        } catch (error) {
          setAlert(alertBox, error.message);
          submit.disabled = false;
        }
      },
    },
    el("p", {}, "Como foi o atendimento?"),
    el("div", { class: "star-row", role: "group", "aria-label": "Nota" }, buttons, hint),
    el("label", { for: "rating-comment", class: "visually-hidden" }, "Comentário da avaliação"),
    comment,
    alertBox,
    el("div", { class: "form-actions" }, submit),
  );
}

function ratingCard() {
  if (ticket.rating) {
    return el(
      "section",
      { class: "card rating-card", "aria-labelledby": "rating-title" },
      el("h3", { class: "card-title", id: "rating-title" }, "Avaliação do atendimento"),
      el("p", {}, stars(ticket.rating), " ", el("strong", {}, RATING_LABELS[ticket.rating])),
      ticket.rating_comment && el("p", { class: "prose" }, ticket.rating_comment),
    );
  }
  const canRate = ticket.status === "FECHADO" && !ticket.is_archived && ticket.requester.id === user.id;
  if (!canRate) return null;
  return el(
    "section",
    { class: "card rating-card", "aria-labelledby": "rating-title" },
    el("h3", { class: "card-title", id: "rating-title" }, "Avalie o atendimento"),
    ratingForm(),
  );
}

function detail(term, value) {
  return [el("dt", {}, term), el("dd", {}, value)];
}

function time(iso) {
  return iso ? el("time", { datetime: iso, title: formatDateTime(iso) }, formatDateTime(iso)) : "—";
}

function detailsCard() {
  return el(
    "section",
    { class: "card", "aria-labelledby": "details-title" },
    el("h3", { class: "card-title", id: "details-title" }, "Detalhes"),
    el(
      "dl",
      { class: "details" },
      detail("Solicitante", ticket.requester.name),
      detail("Responsável", ticket.assigned_to?.name ?? el("span", { class: "muted" }, "Sem responsável")),
      detail("Categoria", ticket.category.name),
      detail("Prioridade", PRIORITY_LABELS[ticket.priority]),
      detail("Aberto em", time(ticket.created_at)),
      detail("Prazo (SLA)", time(ticket.sla_deadline)),
      ticket.resolved_at && detail("Resolvido em", time(ticket.resolved_at)),
      ticket.closed_at && detail("Fechado em", time(ticket.closed_at)),
      detail("Atualizado", el("time", { datetime: ticket.updated_at, title: formatDateTime(ticket.updated_at) }, formatRelative(ticket.updated_at))),
    ),
  );
}

function author(person, when) {
  return el(
    "div",
    { class: "entry-meta" },
    el("span", { class: "avatar avatar-sm", "aria-hidden": "true" }, initials(person.name)),
    el("strong", {}, person.name),
    person.id === ticket.requester.id && el("span", { class: "author-tag" }, "solicitante"),
    person.id === ticket.assigned_to?.id && el("span", { class: "author-tag" }, "responsável"),
    el("time", { datetime: when, title: formatDateTime(when) }, formatRelative(when)),
  );
}

// Respostas prontas: só técnico e admin; carregadas uma vez por tela
let cannedResponses = null;

async function loadCannedResponses() {
  if (user.role === "SOLICITANTE") return [];
  try {
    cannedResponses ??= await api.get("/canned-responses");
  } catch {
    cannedResponses = [];
  }
  return cannedResponses;
}

function cannedPicker(textarea) {
  if (!cannedResponses?.length) return null;
  return el(
    "label",
    { class: "field field-compact canned-picker" },
    el("span", { class: "visually-hidden" }, "Inserir resposta pronta"),
    el(
      "select",
      {
        class: "input",
        onChange: (event) => {
          const chosen = cannedResponses.find((r) => String(r.id) === event.target.value);
          event.target.value = "";
          if (!chosen) return;
          // Insere no ponto do cursor, sem apagar o que já foi escrito
          const { selectionStart: start, selectionEnd: end, value } = textarea;
          textarea.value = value.slice(0, start) + chosen.body + value.slice(end);
          textarea.focus();
          textarea.selectionStart = textarea.selectionEnd = start + chosen.body.length;
        },
      },
      el("option", { value: "" }, "Resposta pronta…"),
      cannedResponses.map((r) => el("option", { value: String(r.id) }, r.title)),
    ),
  );
}

function commentForm() {
  const blocker = commentBlocker(ticket);
  if (blocker) return el("p", { class: "alert alert-info" }, blocker);

  const alertBox = el("p", { class: "alert", role: "alert", hidden: true });
  const message = el("textarea", {
    class: "input",
    id: "comment-message",
    name: "message",
    rows: 3,
    maxlength: 5000,
    placeholder: "Escreva um comentário…",
  });
  const submit = el("button", { type: "submit", class: "button button-primary" }, "Comentar");

  return el(
    "form",
    {
      class: "comment-form",
      onSubmit: async (event) => {
        event.preventDefault();
        setAlert(alertBox, "");
        const text = message.value.trim();
        if (!text) {
          setAlert(alertBox, "Escreva o comentário antes de enviar.");
          message.focus();
          return;
        }
        submit.disabled = true;
        try {
          await api.post(`/tickets/${id}/comments`, { message: text });
          await refresh();
          toast("Comentário enviado.");
          document.querySelector("#comment-message")?.focus();
        } catch (error) {
          setAlert(alertBox, error.message);
          submit.disabled = false;
        }
      },
    },
    el("label", { for: "comment-message", class: "visually-hidden" }, "Novo comentário"),
    message,
    alertBox,
    el("div", { class: "form-actions" }, cannedPicker(message), submit),
  );
}

function commentsCard() {
  return el(
    "section",
    { class: "card", "aria-labelledby": "comments-title" },
    el("h3", { class: "card-title", id: "comments-title" }, `Comentários (${comments.length})`),
    comments.length === 0
      ? el("p", { class: "muted" }, "Nenhum comentário ainda.")
      : el(
          "ol",
          { class: "comment-list" },
          comments.map((c) => el("li", { class: "comment" }, author(c.user, c.created_at), el("p", { class: "prose" }, c.message))),
        ),
    commentForm(),
  );
}

// Como cada evento do histórico aparece na linha do tempo
function describe(entry) {
  const status = (code) => STATUS_LABELS[code] ?? code;
  switch (entry.action) {
    case "CRIADO":
      return "abriu o chamado";
    case "STATUS_ALTERADO":
      return `mudou o status de ${status(entry.old_value)} para ${status(entry.new_value)}`;
    case "REABERTO":
      return "reabriu o chamado";
    case "ATRIBUIDO":
      if (!entry.new_value) return `removeu o responsável (${entry.old_value})`;
      return entry.old_value ? `trocou o responsável de ${entry.old_value} para ${entry.new_value}` : `atribuiu a ${entry.new_value}`;
    case "PRIORIDADE_ALTERADA":
      return `mudou a prioridade de ${PRIORITY_LABELS[entry.old_value]} para ${PRIORITY_LABELS[entry.new_value]}`;
    case "CATEGORIA_ALTERADA":
      return `mudou a categoria de ${entry.old_value} para ${entry.new_value}`;
    case "EDITADO":
      return "editou o título ou a descrição";
    case "SOLUCAO_REGISTRADA":
      return "registrou a solução";
    case "ARQUIVADO":
      return "arquivou o chamado";
    case "AVALIADO":
      return `avaliou o atendimento com ${entry.new_value} de 5`;
    case "FECHADO_AUTOMATICAMENTE":
      return `— o chamado foi fechado automaticamente após ${AUTO_CLOSE_DAYS} dias sem resposta do solicitante`;
  }
  return entry.action;
}

function historyCard() {
  return el(
    "section",
    { class: "card", "aria-labelledby": "history-title" },
    el("h3", { class: "card-title", id: "history-title" }, "Histórico"),
    el(
      "ol",
      { class: "timeline" },
      // Mais recente primeiro
      [...historyItems].reverse().map((entry) =>
        el(
          "li",
          { class: `timeline-item timeline-${entry.action.toLowerCase()}` },
          el("p", {}, el("strong", {}, entry.user.name), " ", describe(entry)),
          entry.action === "EDITADO" &&
            el("details", { class: "timeline-diff" }, el("summary", {}, "Ver alteração"),
              el("p", { class: "diff-old" }, entry.old_value), el("p", { class: "diff-new" }, entry.new_value)),
          el("time", { datetime: entry.created_at, title: formatDateTime(entry.created_at) }, formatRelative(entry.created_at)),
        ),
      ),
    ),
  );
}

function render() {
  document.title = `#${ticket.id} ${ticket.title} · HelpBoard`;
  main.replaceChildren(
    header(),
    el(
      "div",
      { class: "ticket-layout" },
      el("div", { class: "ticket-main" }, descriptionCard(), ratingCard(), commentsCard()),
      el("aside", { class: "ticket-side" }, detailsCard(), historyCard()),
    ),
  );
}

await loadCannedResponses();
render();
