from fastapi import APIRouter, Request

from app.core.deps import CurrentUser, DbSession
from app.core.errors import TooManyRequestsError, UnauthorizedError
from app.core.rate_limit import login_limiter
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.common import error_responses
from app.schemas.user import UserOut
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["autenticação"])


@router.post("/login", response_model=TokenResponse, responses=error_responses(401, 403, 429))
def login(data: LoginRequest, db: DbSession, request: Request):
    """Troca e-mail e senha por um token JWT. Envie o token no header `Authorization: Bearer <token>`.

    E-mail ou senha errados respondem 401; usuário desativado responde 403. Depois de 5 erros em
    1 minuto para o mesmo e-mail e IP, responde 429 com o header `Retry-After` (segundos).
    """
    ip = request.client.host if request.client else "?"
    wait = login_limiter.retry_after(ip, data.email)
    if wait:
        raise TooManyRequestsError(f"Muitas tentativas de login. Tente de novo em {wait} segundos.", wait)
    try:
        user = auth_service.authenticate(db, data.email, data.password)
    except UnauthorizedError:
        login_limiter.fail(ip, data.email)
        raise
    login_limiter.reset(ip, data.email)
    return TokenResponse(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut, responses=error_responses(401))
def me(user: CurrentUser):
    """Dados do usuário dono do token."""
    return user
