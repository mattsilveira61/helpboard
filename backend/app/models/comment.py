from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._types import CreatedAt
from app.models.user import User

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class Comment(Base):
    """Comentários não são editados nem apagados (Regra 12), por isso não há updated_at."""

    __tablename__ = "comments"
    __table_args__ = (CheckConstraint("length(trim(message)) > 0", name="message_not_empty"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id", ondelete="RESTRICT"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[CreatedAt]

    ticket: Mapped["Ticket"] = relationship(back_populates="comments")
    user: Mapped[User] = relationship()
