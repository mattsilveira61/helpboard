from sqlalchemy import CheckConstraint, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._types import CreatedAt


class CannedResponse(Base):
    """Texto pronto que o técnico insere no comentário (ex.: pedir mais informações, avisar de manutenção)."""

    __tablename__ = "canned_responses"
    __table_args__ = (CheckConstraint("length(trim(body)) > 0", name="body_not_empty"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(80), unique=True)
    body: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_at: Mapped[CreatedAt]

    def __repr__(self) -> str:
        return f"<CannedResponse {self.id} {self.title}>"
