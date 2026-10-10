// Peças de chamado usadas em mais de uma tela: selos, prazo de SLA e o que cada perfil pode fazer.
//
// As regras abaixo espelham app/services/tickets.py só para decidir quais botões mostrar.
// Quem garante as permissões é a API: se algo mudar no meio do caminho, ela recusa e a tela mostra o motivo.

import { api } from "./api.js";
import { openDialog } from "./dialog.js";
import { el } from "./dom.js";
import { formatRelative } from "./format.js";
import { PRIORITY_LABELS, SLA_HOURS, STATUS_LABELS } from "./labels.js";

// Última tela de chamados visitada (lista ou quadro, com os filtros): o "Voltar" do detalhe volta para ela
const BACK_KEY = "helpboard.back";

export function rememberBack(url) {
  sessionStorage.setItem(BACK_KEY, url);
}

export function backLink() {
  const href = sessionStorage.getItem(BACK_KEY) ?? "tickets.html";
  const board = href.startsWith("board.html");
  return { href, label: board ? "Voltar para o quadro" : "Voltar para a lista", pageId: board ? "board" : "tickets" };
}

export function statusBadge(status) {
  return el("span", { class: `badge status-${status.toLowerCase()}` }, STATUS_LABELS[status]);
}

export function priorityBadge(priority) {
  return el("span", { class: `badge priority-${priority.toLowerCase()}` }, PRIORITY_LABELS[priority]);
}

/**
 * Situação do prazo: atrasado, perto de vencer, no prazo ou (se já resolvido) cumprido ou não.
 * `short` é o texto enxuto usado na tabela da lista.
 */
export function slaInfo(ticket, now = Date.now()) {
  const deadline = new Date(ticket.sla_deadline).getTime();
  const relative = formatRelative(ticket.sla_deadline, now);
  if (ticket.resolved_at || ticket.status === "FECHADO") {
    const late = ticket.resolved_at && new Date(ticket.resolved_at).getTime() > deadline;
    return late
      ? { kind: "missed", text: "Resolvido fora do prazo", short: "Fora do prazo" }
      : { kind: "met", text: "Resolvido no prazo", short: "No prazo" };
  }
  if (ticket.is_overdue) return { kind: "overdue", text: `Atrasado (venceu ${relative})`, short: `Venceu ${relative}` };
  // Menos de 25% do prazo restante: perto de vencer
  const warning = deadline - now < SLA_HOURS[ticket.priority] * 3600 * 1000 * 0.25;
  return { kind: warning ? "warning" : "ok", text: `Vence ${relative}`, short: `Vence ${relative}` };
}

export function slaBadge(ticket, { short = false } = {}) {
  const info = slaInfo(ticket);
  return el("span", { class: `sla sla-${info.kind}`, title: info.text }, short ? info.short : info.text);
}

// --- Permissões (seções 4 e 5 do Planejamento) ---

const isAdmin = (user) => user.role === "ADMIN";
const isAssignee = (ticket, user) => ticket.assigned_to?.id === user.id;
const isRequester = (ticket, user) => ticket.requester.id === user.id;

/** Campos do formulário que o usuário pode alterar neste chamado. */
export function editableFields(ticket, user) {
  if (ticket.is_archived || ticket.status === "FECHADO") return [];
  if (isAdmin(user)) return ["title", "description", "category_id", "priority"];
  const fields = [];
  if (user.role === "SOLICITANTE" && isRequester(ticket, user) && ticket.status === "ABERTO") {
    fields.push("title", "description", "category_id");
  }
  if (user.role === "TECNICO" && isAssignee(ticket, user)) fields.push("category_id", "priority");
  return fields;
}

// Fluxo de status: quem pode (além do admin) e o que é pedido em cada mudança
const TRANSITIONS = [
  { from: "ABERTO", to: "EM_ANDAMENTO", actor: "RESPONSAVEL", label: "Iniciar atendimento", primary: true },
  { from: "EM_ANDAMENTO", to: "RESOLVIDO", actor: "RESPONSAVEL", label: "Resolver", needs: "solution", primary: true },
  { from: "EM_ANDAMENTO", to: "ABERTO", actor: "RESPONSAVEL", label: "Devolver à fila" },
  { from: "RESOLVIDO", to: "FECHADO", actor: "SOLICITANTE", label: "Aceitar e fechar", primary: true },
  { from: "RESOLVIDO", to: "EM_ANDAMENTO", actor: "SOLICITANTE", label: "Recusar solução", needs: "reason" },
  { from: "FECHADO", to: "ABERTO", actor: "SOLICITANTE", label: "Reabrir", needs: "reason" },
];

export function findTransition(from, to) {
  return TRANSITIONS.find((t) => t.from === from && t.to === to) ?? null;
}

/** Mudanças de status que o usuário pode fazer agora neste chamado. */
export function statusActions(ticket, user) {
  if (ticket.is_archived) return [];
  return TRANSITIONS.filter((t) => {
    if (t.from !== ticket.status) return false;
    // Para iniciar o atendimento, o chamado precisa de responsável
    if (t.to === "EM_ANDAMENTO" && t.from === "ABERTO" && !ticket.assigned_to) return false;
    if (isAdmin(user)) return true;
    return t.actor === "RESPONSAVEL" ? isAssignee(ticket, user) : isRequester(ticket, user);
  });
}

/** Por que o chamado não pode ir para o status `to` (usado quando um cartão é solto na coluna errada). */
export function moveBlocker(ticket, user, to) {
  const transition = findTransition(ticket.status, to);
  if (!transition) {
    return `Um chamado ${STATUS_LABELS[ticket.status].toLowerCase()} não pode ir direto para ${STATUS_LABELS[to]}.`;
  }
  if (to === "EM_ANDAMENTO" && ticket.status === "ABERTO" && !ticket.assigned_to) {
    return "Atribua um responsável antes de iniciar o atendimento.";
  }
  return transition.actor === "RESPONSAVEL"
    ? "Só o técnico responsável pelo chamado pode fazer esta mudança."
    : "Só quem abriu o chamado pode fazer esta mudança.";
}

/**
 * Pede a mudança de status à API. Quando ela exige solução ou motivo, abre o diálogo antes
 * (e os erros da API aparecem dentro dele). Devolve true se o status mudou e false se a pessoa cancelou.
 */
export async function requestStatusChange(ticket, transition) {
  const body = { status: transition.to };
  const send = () => api.post(`/tickets/${ticket.id}/status`, body);
  if (!transition.needs) {
    await send();
    return true;
  }

  const isSolution = transition.needs === "solution";
  const saved = await openDialog({
    title: transition.label,
    text: isSolution
      ? "Descreva o que foi feito. O solicitante vai ler a solução para aceitar ou recusar."
      : transition.to === "ABERTO"
        ? "Conte por que o chamado precisa ser reaberto. O motivo vira um comentário."
        : "Conte o que ainda não está resolvido. O motivo vira um comentário e o chamado volta para o técnico.",
    fields: [
      {
        name: "text",
        label: isSolution ? "Solução" : "Motivo",
        type: "textarea",
        value: isSolution ? (ticket.solution ?? "") : "",
        required: !(isSolution && ticket.solution),
      },
    ],
    confirmLabel: transition.label,
    onConfirm: async ({ text }) => {
      if (text.trim()) body[transition.needs] = text.trim();
      await send();
      return true;
    },
  });
  return Boolean(saved);
}

export function canAssume(ticket, user) {
  return user.role === "TECNICO" && !ticket.is_archived && ticket.status === "ABERTO" && !ticket.assigned_to;
}

export function canAssign(ticket, user) {
  return isAdmin(user) && !ticket.is_archived && ["ABERTO", "EM_ANDAMENTO"].includes(ticket.status);
}

export function canArchive(ticket, user) {
  return isAdmin(user) && !ticket.is_archived;
}

/** Motivo para não poder comentar, ou null se pode. */
export function commentBlocker(ticket) {
  if (ticket.is_archived) return "Chamado arquivado não recebe comentários.";
  if (ticket.status === "FECHADO") return "Chamado fechado não recebe comentários. Reabra o chamado para continuar a conversa.";
  return null;
}
