from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, StringConstraints

from app.models import Role

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=100)]


def _check_password_bytes(value: str) -> str:
    # O bcrypt só aceita até 72 bytes (letras com acento ocupam 2 bytes cada)
    if len(value.encode()) > 72:
        raise ValueError("A senha pode ter no máximo 72 bytes.")
    return value


Password = Annotated[str, Field(min_length=8), AfterValidator(_check_password_bytes)]


class UserCreate(BaseModel):
    name: Name
    email: EmailStr
    password: Password
    role: Role


class UserUpdate(BaseModel):
    """Todos os campos são opcionais: só o que for enviado é alterado."""

    name: Name | None = None
    email: EmailStr | None = None
    password: Password | None = None
    role: Role | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    """Formato de saída: nunca inclui a senha nem o hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: Role
    is_active: bool
    created_at: datetime
