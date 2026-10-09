"""Regras de negócio dos chamados (seções 3 a 6 do Planejamento).

Toda alteração grava o histórico na mesma sessão e só depois faz um único commit:
ou a mudança e o histórico são salvos juntos, ou nada é salvo (Regra 8).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.clock import start_of_day
from app.core.errors import ConflictError, ForbiddenError, NotFoundError
from app.models import Category, Comment, HistoryAction, Priority, Role, Ticket, TicketHistory, TicketStatus, User
from app.schemas.ticket import StatusChange, TicketCreate, TicketFilters, TicketUpdate
from app.services.sla import calculate_sla_deadline

A, E, R, F = TicketStatus.ABERTO, TicketStatus.EM_ANDAMENTO, TicketStatus.RESOLVIDO, TicketStatus.FECHADO

# Regra 10: CRÍTICA primeiro
PRIORITY_ORDER = case(
    {Priority.CRITICA: 0, Priority.ALTA: 1, Priority.MEDIA: 2, Priority.BAIXA: 3}, value=Ticket.priority
)


@dataclass(frozen=True)
class Transition:
    # Além do admin, quem pode fazer a transição: o técnico responsável ou o solicitante do chamado
    actor: Literal["RESPONSAVEL", "SOLICITANTE"]
    needs_solution: bool = False
    needs_reason: bool = False


# Seção 4 do Planejamento: qualquer par fora desta tabela é recusado
TRANSITIONS: dict[tuple[TicketStatus, TicketStatus], Transition] = {
    (A, E): Transition("RESPONSAVEL"),
    (E, A): Transition("RESPONSAVEL"),
    (E, R): Transition("RESPONSAVEL", needs_solution=True),
    (R, E): Transition("SOLICITANTE", needs_reason=True),
    (R, F): Transition("SOLICITANTE"),
    (F, A): Transition("SOLICITANTE", needs_reason=True),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _log(
    db: Session, ticket: Ticket, user: User, action: HistoryAction, old: object = None, new: object = None
) -> None:
    db.add(
        TicketHistory(
            ticket=ticket,
            user=user,
            action=action,
            old_value=None if old is None else str(old),
            new_value=None if new is None else str(new),
            created_at=_now(),
        )
    )


# --- Visibilidade (seção 3) ---


def _visible_query(user: User, include_archived: bool = False) -> Select[tuple[Ticket]]:
    query = select(Ticket).options(
        selectinload(Ticket.category), selectinload(Ticket.requester), selectinload(Ticket.assigned_to)
    )
    if user.role == Role.TECNICO:
        # Os atribuídos a ele, os disponíveis (sem responsável) e os que ele mesmo abriu
        query = query.where(
            or_(Ticket.assigned_to_id == user.id, Ticket.assigned_to_id.is_(None), Ticket.requester_id == user.id)
        )
    elif user.role == Role.SOLICITANTE:
        query = query.where(Ticket.requester_id == user.id)

    # Arquivados ficam ocultos; só o admin pode pedir para vê-los
    if not (include_archived and user.role == Role.ADMIN):
        query = query.where(Ticket.is_archived.is_(False))
    return query


def _apply_filters(query: Select[tuple[Ticket]], filters: TicketFilters) -> Select[tuple[Ticket]]:
    if filters.status:
        query = query.where(Ticket.status.in_(filters.status))
    if filters.priority:
        query = query.where(Ticket.priority.in_(filters.priority))
    if filters.category_id is not None:
        query = query.where(Ticket.category_id == filters.category_id)
    if filters.unassigned:
        query = query.where(Ticket.assigned_to_id.is_(None))
    elif filters.assigned_to_id is not None:
        query = query.where(Ticket.assigned_to_id == filters.assigned_to_id)
    if filters.requester_id is not None:
        query = query.where(Ticket.requester_id == filters.requester_id)
    if filters.created_from:
        query = query.where(Ticket.created_at >= start_of_day(filters.created_from))
    if filters.created_to:
        query = query.where(Ticket.created_at < start_of_day(filters.created_to + timedelta(days=1)))
    if filters.q:
        # Os curingas do LIKE digitados pelo usuário são tratados como texto comum
        escaped = filters.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        conditions = [Ticket.title.ilike(pattern, escape="\\"), Ticket.description.ilike(pattern, escape="\\")]
        ticket_id = filters.q.removeprefix("#")
        if ticket_id.isdigit() and int(ticket_id) < 2**31:
            conditions.append(Ticket.id == int(ticket_id))
        query = query.where(or_(*conditions))
    return query


def list_tickets(db: Session, user: User, filters: TicketFilters) -> tuple[list[Ticket], int]:
    """Devolve a página pedida e o total de chamados que atendem aos filtros."""
    query = _apply_filters(_visible_query(user, filters.include_archived), filters)

    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    page = query.order_by(PRIORITY_ORDER, Ticket.created_at, Ticket.id)
    page = page.limit(filters.page_size).offset((filters.page - 1) * filters.page_size)
    return list(db.scalars(page)), total


def get_ticket(db: Session, ticket_id: int, user: User) -> Ticket:
    """Chamado que o usuário não pode ver responde 404, para não revelar que ele existe."""
    ticket = db.scalar(_visible_query(user, include_archived=True).where(Ticket.id == ticket_id))
    if ticket is None:
        raise NotFoundError("Chamado não encontrado.")
    return ticket


# --- Validações compartilhadas ---


def _active_category(db: Session, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None or not category.is_active:
        raise ConflictError("Categoria não encontrada ou inativa.")
    return category


def _ensure_editable(ticket: Ticket) -> None:
    if ticket.is_archived:
        raise ConflictError("Chamado arquivado não pode ser alterado.")


# --- Criação e edição ---


def create_ticket(db: Session, data: TicketCreate, user: User) -> Ticket:
    category = _active_category(db, data.category_id)  # Regra 1
    now = _now()
    ticket = Ticket(
        title=data.title,
        description=data.description,
        category=category,
        priority=data.priority,
        requester=user,  # Regra 2
        status=A,  # Regra 3
        sla_deadline=calculate_sla_deadline(now, data.priority),  # Regra 11
        created_at=now,
        updated_at=now,
    )
    db.add(ticket)
    _log(db, ticket, user, HistoryAction.CRIADO, new=A)
    db.commit()
    return ticket


def _can_edit(field: str, ticket: Ticket, user: User) -> bool:
    """Matriz de permissões (seção 5) para cada campo editável."""
    if user.role == Role.ADMIN:
        return True
    own_and_open = user.role == Role.SOLICITANTE and ticket.requester_id == user.id and ticket.status == A
    is_assignee = user.role == Role.TECNICO and ticket.assigned_to_id == user.id
    match field:
        case "title" | "description":
            return own_and_open
        case "category_id":
            return own_and_open or is_assignee
        case "priority":
            return is_assignee
    return False


def update_ticket(db: Session, ticket: Ticket, data: TicketUpdate, user: User) -> Ticket:
    _ensure_editable(ticket)
    if ticket.status == F:
        raise ConflictError("Chamado fechado não pode ser alterado. Reabra o chamado primeiro.")

    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    denied = [field for field in changes if not _can_edit(field, ticket, user)]
    if denied:
        raise ForbiddenError(f"Você não tem permissão para alterar: {', '.join(denied)}.")

    for field in ("title", "description"):
        if field in changes and changes[field] != getattr(ticket, field):
            _log(db, ticket, user, HistoryAction.EDITADO, getattr(ticket, field), changes[field])
            setattr(ticket, field, changes[field])

    if "category_id" in changes and changes["category_id"] != ticket.category_id:
        category = _active_category(db, changes["category_id"])
        _log(db, ticket, user, HistoryAction.CATEGORIA_ALTERADA, ticket.category.name, category.name)
        ticket.category = category

    if "priority" in changes and changes["priority"] != ticket.priority:
        _log(db, ticket, user, HistoryAction.PRIORIDADE_ALTERADA, ticket.priority, changes["priority"])
        ticket.priority = changes["priority"]
        # Regra 11: o prazo é recalculado a partir da abertura com a nova prioridade
        ticket.sla_deadline = calculate_sla_deadline(ticket.created_at, ticket.priority)

    db.commit()
    return ticket


# --- Responsável (Regra 4) ---


def _set_assignee(db: Session, ticket: Ticket, assignee: User | None, actor: User) -> None:
    old_name = ticket.assigned_to.name if ticket.assigned_to else None
    ticket.assigned_to = assignee
    _log(db, ticket, actor, HistoryAction.ATRIBUIDO, old_name, assignee.name if assignee else None)


def assign_ticket(db: Session, ticket: Ticket, assignee_id: int | None, actor: User) -> Ticket:
    """Admin atribui, reatribui ou remove o responsável."""
    _ensure_editable(ticket)
    if ticket.status not in (A, E):
        raise ConflictError("Só é possível alterar o responsável de chamados abertos ou em andamento.")
    if ticket.assigned_to_id == assignee_id:
        return ticket

    assignee = None
    if assignee_id is None:
        if ticket.status == E:
            raise ConflictError("Chamado em andamento precisa de responsável. Devolva-o à fila (ABERTO) antes.")
    else:
        assignee = db.get(User, assignee_id)
        if assignee is None or not assignee.is_active or assignee.role not in (Role.TECNICO, Role.ADMIN):
            raise ConflictError("O responsável precisa ser um técnico ou admin ativo.")

    _set_assignee(db, ticket, assignee, actor)
    db.commit()
    return ticket


def assume_ticket(db: Session, ticket: Ticket, user: User) -> Ticket:
    """O técnico se autoatribui um chamado ABERTO e sem responsável."""
    _ensure_editable(ticket)
    if ticket.status != A or ticket.assigned_to_id is not None:
        raise ConflictError("Só é possível assumir chamados abertos e sem responsável.")

    _set_assignee(db, ticket, user, user)
    db.commit()
    return ticket


# --- Mudança de status (seção 4, Regras 5 e 6) ---


def _can_transition(transition: Transition, ticket: Ticket, user: User) -> bool:
    if user.role == Role.ADMIN:
        return True
    if transition.actor == "RESPONSAVEL":
        return ticket.assigned_to_id == user.id
    return ticket.requester_id == user.id


def change_status(db: Session, ticket: Ticket, data: StatusChange, user: User) -> Ticket:
    _ensure_editable(ticket)
    old, new = ticket.status, data.status

    transition = TRANSITIONS.get((old, new))
    if transition is None:
        raise ConflictError(f"Transição de {old} para {new} não é permitida.")
    if not _can_transition(transition, ticket, user):
        raise ForbiddenError("Você não tem permissão para fazer esta mudança de status.")

    if new == E and ticket.assigned_to_id is None:
        raise ConflictError("Atribua um responsável antes de iniciar o atendimento.")
    if transition.needs_solution and not (data.solution or ticket.solution):
        raise ConflictError("Informe a solução para resolver o chamado.")
    if transition.needs_reason and not data.reason:
        raise ConflictError("Informe o motivo.")

    now = _now()
    match (old, new):
        case (TicketStatus.EM_ANDAMENTO, TicketStatus.ABERTO):
            _set_assignee(db, ticket, None, user)  # devolver à fila
        case (_, TicketStatus.RESOLVIDO):
            if data.solution and data.solution != ticket.solution:
                _log(db, ticket, user, HistoryAction.SOLUCAO_REGISTRADA, ticket.solution, data.solution)
                ticket.solution = data.solution
            ticket.resolved_at = now
        case (TicketStatus.RESOLVIDO, TicketStatus.EM_ANDAMENTO):
            ticket.resolved_at = None  # solução recusada
        case (_, TicketStatus.FECHADO):
            ticket.closed_at = now
        case (TicketStatus.FECHADO, TicketStatus.ABERTO):
            # A solução antiga continua registrada no histórico (evento SOLUCAO_REGISTRADA)
            ticket.solution = ticket.resolved_at = ticket.closed_at = None

    if data.reason:
        db.add(Comment(ticket=ticket, user=user, message=data.reason, created_at=now))

    action = HistoryAction.REABERTO if old == F else HistoryAction.STATUS_ALTERADO
    _log(db, ticket, user, action, old, new)
    ticket.status = new
    db.commit()
    return ticket


# --- Arquivamento (Regra 9) ---


def archive_ticket(db: Session, ticket: Ticket, user: User) -> Ticket:
    if ticket.is_archived:
        raise ConflictError("Chamado já está arquivado.")
    ticket.is_archived = True
    _log(db, ticket, user, HistoryAction.ARQUIVADO)
    db.commit()
    return ticket
