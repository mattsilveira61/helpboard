from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._types import CreatedAt, enum_column
from app.models.enums import HistoryAction
from app.models.user import User

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class TicketHistory(Base):
    """Registro de auditoria: cada mudança relevante do chamado gera uma linha (Regra 8)."""

    __tablename__ = "ticket_history"
    # A tela de detalhe lista o histórico de um chamado em ordem cronológica
    __table_args__ = (Index(None, "ticket_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="RESTRICT"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[HistoryAction] = mapped_column(enum_column(HistoryAction, "history_action"))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[CreatedAt]

    ticket: Mapped["Ticket"] = relationship(back_populates="history")
    user: Mapped[User] = relationship()
