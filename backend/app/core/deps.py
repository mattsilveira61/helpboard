"""Dependências do FastAPI para autenticação e controle de acesso por perfil."""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import decode_access_token
from app.models import Role, User

bearer_scheme = HTTPBearer(auto_error=False, description="Token JWT obtido em POST /auth/login")

DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None:
        raise UnauthorizedError("Não autenticado.")

    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id) if user_id is not None else None
    # Usuário desativado perde o acesso na hora, mesmo que o token ainda esteja dentro da validade
    if user is None or not user.is_active:
        raise UnauthorizedError("Token inválido ou expirado.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    """Cria uma dependência que só deixa passar os perfis informados."""

    def dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError("Seu perfil não tem permissão para esta ação.")
        return user

    return dependency
