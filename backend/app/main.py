from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError, UnauthorizedError
from app.routers import auth, categories, comments, dashboard, tickets, users

settings = get_settings()

app = FastAPI(
    title="HelpBoard API",
    description=(
        "Sistema de gestão de chamados e suporte com quadro Kanban.\n\n"
        "Faça login em `POST /auth/login`, clique em **Authorize** e cole o `access_token`. "
        "Usuários de demonstração: `admin@`, `maria@`, `carlos@` e `joao@helpboard.dev`."
    ),
    version="0.1.0",
    openapi_tags=[
        {"name": "autenticação", "description": "Login e dados do usuário logado"},
        {"name": "usuários", "description": "Gerenciamento de usuários (só admin)"},
        {"name": "categorias", "description": "Categorias dos chamados (leitura para todos, alteração só admin)"},
        {"name": "chamados", "description": "Abertura, edição, atribuição, fluxo de status e arquivamento"},
        {"name": "comentários e histórico", "description": "Conversa e linha do tempo de cada chamado"},
        {"name": "dashboard", "description": "Indicadores de gestão (admin vê tudo, técnico vê os seus números)"},
        {"name": "infra", "description": "Verificação de saúde da API"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Converte os erros de regra de negócio dos services em respostas HTTP."""
    headers = {"WWW-Authenticate": "Bearer"} if isinstance(exc, UnauthorizedError) else None
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=headers)


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(categories.router)
app.include_router(tickets.router)
app.include_router(comments.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["infra"])
def health(db: Session = Depends(get_db)):
    """Verifica se a API está no ar e se o banco responde."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "error", "database": "unavailable"})
    return {"status": "ok", "database": "ok"}
