from functools import lru_cache

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import hash_password, verify_password
from app.models import User


@lru_cache
def _dummy_hash() -> str:
    return hash_password("senha-que-nao-existe")


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))

    # A senha é conferida mesmo quando o e-mail não existe: assim a resposta demora o mesmo
    # tempo nos dois casos e não revela quais e-mails estão cadastrados.
    password_ok = verify_password(password, user.password_hash if user else _dummy_hash())
    if user is None or not password_ok:
        raise UnauthorizedError("E-mail ou senha inválidos.")

    # Regra 13: usuário desativado não loga
    if not user.is_active:
        raise ForbiddenError("Usuário desativado. Procure o administrador.")
    return user
