from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.models import Role
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services import users as user_service

# Gerenciar usuários é exclusivo do admin (matriz de permissões): a checagem vale para todas as rotas
router = APIRouter(prefix="/users", tags=["usuários"], dependencies=[Depends(require_roles(Role.ADMIN))])


@router.get("", response_model=list[UserOut])
def list_users(db: DbSession, active: bool | None = None, role: Role | None = None):
    """Lista os usuários em ordem alfabética, com filtros opcionais por situação e perfil."""
    return user_service.list_users(db, active=active, role=role)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: DbSession):
    return user_service.create_user(db, data)


@router.get("/{user_id}", response_model=UserOut)
def get_user(user_id: int, db: DbSession):
    return user_service.get_user(db, user_id)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: int, data: UserUpdate, db: DbSession, actor: CurrentUser):
    """Altera só os campos enviados. `is_active: true` reativa um usuário desativado."""
    return user_service.update_user(db, user_service.get_user(db, user_id), data, actor)


@router.delete("/{user_id}", response_model=UserOut)
def deactivate_user(user_id: int, db: DbSession, actor: CurrentUser):
    """Desativa o usuário. Não existe exclusão física: os chamados dele continuam no sistema."""
    return user_service.deactivate_user(db, user_service.get_user(db, user_id), actor)
