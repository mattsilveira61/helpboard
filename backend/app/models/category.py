from sqlalchemy import String, Text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._types import CreatedAt


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_at: Mapped[CreatedAt]

    def __repr__(self) -> str:
        return f"<Category {self.id} {self.name}>"
