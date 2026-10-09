from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import DbSession, require_roles
from app.models import Role, User
from app.schemas.common import error_responses
from app.schemas.dashboard import DashboardOut, DashboardParams
from app.services import dashboard as dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"], responses=error_responses(401, 403))


@router.get("", response_model=DashboardOut)
def get_dashboard(
    db: DbSession,
    user: Annotated[User, Depends(require_roles(Role.ADMIN, Role.TECNICO))],
    params: Annotated[DashboardParams, Query()],
):
    """Indicadores de gestão. O admin vê todos os chamados; o técnico, só os atribuídos a ele.

    `backlog` é a fila de agora. `created`, `resolved`, `timeline` e `by_assignee` usam o período
    (`start` e `end`, padrão: os últimos 30 dias). Chamados arquivados não entram na conta.
    """
    return dashboard_service.get_dashboard(db, user, params)
