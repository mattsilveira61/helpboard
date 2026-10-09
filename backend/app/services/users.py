from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models import Role, User
from app.schemas.user import UserCreate, UserUpdate


def list_users(db: Session, *, active: bool | None = None, role: Role | None = None) -> list[User]:
    query = select(User).order_by(User.name)
    if active is not None:
        query = query.where(User.is_active == active)
    if role is not None:
        query = query.where(User.role == role)
    return list(db.scalars(query))


def get_user(db: Session, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("Usuário não encontrado.")
    return user


def _ensure_email_available(db: Session, email: str, exclude_id: int | None = None) -> None:
    query = select(User.id).where(User.email == email)
    if exclude_id is not None:
        query = query.where(User.id != exclude_id)
    if db.scalar(query) is not None:
        raise ConflictError("Já existe um usuário com este e-mail.")


def create_user(db: Session, data: UserCreate) -> User:
    # E-mail sempre em minúsculas: "Joao@x.com" e "joao@x.com" são o mesmo usuário
    email = data.email.lower()
    _ensure_email_available(db, email)

    user = User(name=data.name, email=email, role=data.role, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def update_user(db: Session, user: User, data: UserUpdate, actor: User) -> User:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)

    # Impede que o admin se tranque para fora do sistema (Regra 13)
    if user.id == actor.id:
        if changes.get("is_active") is False:
            raise ConflictError("Você não pode desativar o próprio usuário.")
        if changes.get("role", Role.ADMIN) != Role.ADMIN:
            raise ConflictError("Você não pode remover o próprio perfil de administrador.")

    if "email" in changes:
        changes["email"] = changes["email"].lower()
        _ensure_email_available(db, changes["email"], exclude_id=user.id)
    if "password" in changes:
        changes["password_hash"] = hash_password(changes.pop("password"))

    for field, value in changes.items():
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user


def deactivate_user(db: Session, user: User, actor: User) -> User:
    """Regra 9: usuário nunca é apagado, só desativado (os chamados dele continuam no histórico)."""
    return update_user(db, user, UserUpdate(is_active=False), actor)
