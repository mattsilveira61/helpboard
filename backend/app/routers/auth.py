from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.user import UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["autenticação"])


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: DbSession):
    """Troca e-mail e senha por um token JWT. Envie o token no header `Authorization: Bearer <token>`."""
    user = auth_service.authenticate(db, data.email, data.password)
    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    """Dados do usuário dono do token."""
    return user
