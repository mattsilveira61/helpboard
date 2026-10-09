from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models import Category
from app.schemas.category import CategoryCreate, CategoryUpdate


def list_categories(db: Session, *, include_inactive: bool = False) -> list[Category]:
    query = select(Category).order_by(Category.name)
    if not include_inactive:
        query = query.where(Category.is_active.is_(True))
    return list(db.scalars(query))


def get_category(db: Session, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise NotFoundError("Categoria não encontrada.")
    return category


def _ensure_name_available(db: Session, name: str, exclude_id: int | None = None) -> None:
    # Regra 14: nome único, sem diferenciar maiúsculas ("rede" e "Rede" são a mesma categoria)
    query = select(Category.id).where(func.lower(Category.name) == name.lower())
    if exclude_id is not None:
        query = query.where(Category.id != exclude_id)
    if db.scalar(query) is not None:
        raise ConflictError("Já existe uma categoria com este nome.")


def create_category(db: Session, data: CategoryCreate) -> Category:
    _ensure_name_available(db, data.name)
    category = Category(name=data.name, description=data.description or None)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, category: Category, data: CategoryUpdate) -> Category:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in changes:
        _ensure_name_available(db, changes["name"], exclude_id=category.id)
    if "description" in changes:
        # Enviar "" apaga a descrição
        changes["description"] = changes["description"] or None

    for field, value in changes.items():
        setattr(category, field, value)
    db.commit()
    db.refresh(category)
    return category


def deactivate_category(db: Session, category: Category) -> Category:
    """Regra 14: a categoria some dos formulários, mas continua nos chamados antigos."""
    return update_category(db, category, CategoryUpdate(is_active=False))
