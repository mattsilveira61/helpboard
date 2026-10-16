from fastapi import APIRouter, Depends, status

from app.core.deps import DbSession, require_roles
from app.models import Role, User
from app.schemas.canned_response import CannedResponseCreate, CannedResponseOut, CannedResponseUpdate
from app.schemas.common import error_responses
from app.services import canned_responses as service

router = APIRouter(prefix="/canned-responses", tags=["respostas prontas"], responses=error_responses(401, 403))

admin_only = [Depends(require_roles(Role.ADMIN))]
staff = require_roles(Role.ADMIN, Role.TECNICO)


@router.get("", response_model=list[CannedResponseOut])
def list_responses(db: DbSession, user: User = Depends(staff), include_inactive: bool = False):
    """Respostas prontas em ordem alfabética (admin e técnico). Por padrão, só as ativas.

    `include_inactive=true` traz também as inativas, mas só para o admin.
    """
    include_inactive = include_inactive and user.role == Role.ADMIN
    return service.list_responses(db, include_inactive=include_inactive)


@router.post(
    "",
    response_model=CannedResponseOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=admin_only,
    responses=error_responses(409),
)
def create_response(data: CannedResponseCreate, db: DbSession):
    return service.create_response(db, data)


@router.patch(
    "/{response_id}", response_model=CannedResponseOut, dependencies=admin_only, responses=error_responses(404, 409)
)
def update_response(response_id: int, data: CannedResponseUpdate, db: DbSession):
    """Altera só os campos enviados. `is_active: true` reativa a resposta."""
    return service.update_response(db, service.get_response(db, response_id), data)


@router.delete(
    "/{response_id}", response_model=CannedResponseOut, dependencies=admin_only, responses=error_responses(404)
)
def deactivate_response(response_id: int, db: DbSession):
    """Desativa a resposta: ela some do seletor dos técnicos."""
    return service.deactivate_response(db, service.get_response(db, response_id))
