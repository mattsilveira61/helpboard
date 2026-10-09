"""Comentários e histórico de um chamado.

Quem pode ver o chamado pode ler e comentar (matriz da seção 5); a checagem de visibilidade
fica no `get_ticket` do service de chamados, chamado antes destas funções.
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import ConflictError
from app.models import Comment, Ticket, TicketHistory, TicketStatus, User


def list_comments(db: Session, ticket: Ticket) -> list[Comment]:
    query = (
        select(Comment)
        .options(selectinload(Comment.user))
        .where(Comment.ticket_id == ticket.id)
        .order_by(Comment.created_at, Comment.id)
    )
    return list(db.scalars(query))


def add_comment(db: Session, ticket: Ticket, message: str, user: User) -> Comment:
    # Regra 12: para comentar num chamado fechado, é preciso reabri-lo (com motivo)
    if ticket.status == TicketStatus.FECHADO:
        raise ConflictError("Não é possível comentar em chamado fechado. Reabra o chamado primeiro.")
    if ticket.is_archived:
        raise ConflictError("Não é possível comentar em chamado arquivado.")

    comment = Comment(ticket=ticket, user=user, message=message, created_at=datetime.now(timezone.utc))
    db.add(comment)
    db.commit()
    return comment


def list_history(db: Session, ticket: Ticket) -> list[TicketHistory]:
    query = (
        select(TicketHistory)
        .options(selectinload(TicketHistory.user))
        .where(TicketHistory.ticket_id == ticket.id)
        .order_by(TicketHistory.created_at, TicketHistory.id)
    )
    return list(db.scalars(query))
