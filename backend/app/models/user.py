from sqlalchemy import String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models._types import CreatedAt, enum_column
from app.models.enums import Role


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    # Guardado sempre em minúsculas (normalizado no service) para a unicidade valer sem diferenciar maiúsculas
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(enum_column(Role, "user_role"))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    created_at: Mapped[CreatedAt]

    def __repr__(self) -> str:
        return f"<User {self.id} {self.email} {self.role}>"
