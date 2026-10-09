// Peças de chamado usadas em mais de uma tela: selos, prazo de SLA e o que cada perfil pode fazer.
//
// As regras abaixo espelham app/services/tickets.py só para decidir quais botões mostrar.
// Quem garante as permissões é a API: se algo mudar no meio do caminho, ela recusa e a tela mostra o motivo.

import { el } from "./dom.js";
import { formatRelative } from "./format.js";
import { PRIORITY_LABELS, SLA_HOURS, STATUS_LABELS } from "./labels.js";

// Última busca feita na lista: o "Voltar" do detalhe cai na mesma página e com os mesmos filtros
export const LAST_LIST_KEY = "helpboard.lastList";

export function listUrl() {
  return `tickets.html${sessionStorage.getItem(LAST_LIST_KEY) ?? ""}`;
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
