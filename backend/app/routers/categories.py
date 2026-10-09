from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.models import Role
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate
from app.schemas.common import error_responses
from app.services import categories as category_service

router = APIRouter(prefix="/categories", tags=["categorias"], responses=error_responses(401))

admin_only = [Depends(require_roles(Role.ADMIN))]


@router.get("", response_model=list[CategoryOut])
def list_categories(db: DbSession, user: CurrentUser, include_inactive: bool = False):
    """Lista as categorias em ordem alfabética. Por padrão, só as ativas (as que aparecem no formulário).

    `include_inactive=true` traz também as inativas, mas só para o admin.
    """
    include_inactive = include_inactive and user.role == Role.ADMIN
    return category_service.list_categories(db, include_inactive=include_inactive)


@router.post(
    "",
    response_model=CategoryOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=admin_only,
    responses=error_responses(403, 409),
)
def create_category(data: CategoryCreate, db: DbSession):
    return category_service.create_category(db, data)


@router.get("/{category_id}", response_model=CategoryOut, responses=error_responses(404))
def get_category(category_id: int, db: DbSession, user: CurrentUser):
    return category_service.get_category(db, category_id)


@router.patch(
    "/{category_id}", response_model=CategoryOut, dependencies=admin_only, responses=error_responses(403, 404, 409)
)
def update_category(category_id: int, data: CategoryUpdate, db: DbSession):
    """Altera só os campos enviados. `is_active: true` reativa a categoria."""
    return category_service.update_category(db, category_service.get_category(db, category_id), data)


@router.delete(
    "/{category_id}", response_model=CategoryOut, dependencies=admin_only, responses=error_responses(403, 404)
)
def deactivate_category(category_id: int, db: DbSession):
    """Desativa a categoria. Ela some do formulário, mas os chamados antigos continuam com ela."""
    return category_service.deactivate_category(db, category_service.get_category(db, category_id))
