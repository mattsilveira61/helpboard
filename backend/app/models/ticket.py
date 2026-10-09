from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, false, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._types import CreatedAt, enum_column
from app.models.category import Category
from app.models.enums import Priority, TicketStatus
from app.models.user import User

if TYPE_CHECKING:
    from app.models.comment import Comment
    from app.models.ticket_history import TicketHistory


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("char_length(trim(title)) BETWEEN 3 AND 120", name="title_length"),
        # Regra 5: chamado resolvido (ou fechado depois de resolvido) precisa ter a solução registrada
        CheckConstraint(
            "status NOT IN ('RESOLVIDO', 'FECHADO') OR solution IS NOT NULL", name="solution_required"
        ),
        CheckConstraint(
            "status NOT IN ('RESOLVIDO', 'FECHADO') OR resolved_at IS NOT NULL",
            name="resolved_at_required",
        ),
        CheckConstraint("status <> 'FECHADO' OR closed_at IS NOT NULL", name="closed_at_required"),
        # Só entra em andamento com responsável (seção 4 do planejamento)
        CheckConstraint(
            "status <> 'EM_ANDAMENTO' OR assigned_to_id IS NOT NULL", name="in_progress_has_assignee"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[TicketStatus] = mapped_column(
        enum_column(TicketStatus, "ticket_status"),
        default=TicketStatus.ABERTO,
        server_default=TicketStatus.ABERTO.value,
        index=True,
    )
    priority: Mapped[Priority] = mapped_column(enum_column(Priority, "ticket_priority"), index=True)

    # ON DELETE RESTRICT: nada é apagado em cascata (Regra 9)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    assigned_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )

    sla_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    solution: Mapped[str | None] = mapped_column(Text)
    is_archived: Mapped[bool] = mapped_column(default=False, server_default=false())

    created_at: Mapped[CreatedAt] = mapped_column(index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    category: Mapped[Category] = relationship()
    requester: Mapped[User] = relationship(foreign_keys=[requester_id])
    assigned_to: Mapped[User | None] = relationship(foreign_keys=[assigned_to_id])
    comments: Mapped[list["Comment"]] = relationship(back_populates="ticket", order_by="Comment.created_at")
    history: Mapped[list["TicketHistory"]] = relationship(
        back_populates="ticket", order_by="TicketHistory.created_at"
    )

    def __repr__(self) -> str:
        return f"<Ticket {self.id} {self.status} {self.priority}>"
