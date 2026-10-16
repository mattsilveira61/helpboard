from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.models import CannedResponse
from app.schemas.canned_response import CannedResponseCreate, CannedResponseUpdate


def list_responses(db: Session, *, include_inactive: bool = False) -> list[CannedResponse]:
    query = select(CannedResponse).order_by(CannedResponse.title)
    if not include_inactive:
        query = query.where(CannedResponse.is_active.is_(True))
    return list(db.scalars(query))


def get_response(db: Session, response_id: int) -> CannedResponse:
    response = db.get(CannedResponse, response_id)
    if response is None:
        raise NotFoundError("Resposta pronta não encontrada.")
    return response


def _ensure_title_available(db: Session, title: str, exclude_id: int | None = None) -> None:
    # Título único sem diferenciar maiúsculas, como o nome das categorias
    query = select(CannedResponse.id).where(func.lower(CannedResponse.title) == title.lower())
    if exclude_id is not None:
        query = query.where(CannedResponse.id != exclude_id)
    if db.scalar(query) is not None:
        raise ConflictError("Já existe uma resposta pronta com este título.")


def create_response(db: Session, data: CannedResponseCreate) -> CannedResponse:
    _ensure_title_available(db, data.title)
    response = CannedResponse(title=data.title, body=data.body)
    db.add(response)
    db.commit()
    db.refresh(response)
    return response


def update_response(db: Session, response: CannedResponse, data: CannedResponseUpdate) -> CannedResponse:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "title" in changes:
        _ensure_title_available(db, changes["title"], exclude_id=response.id)
    for field, value in changes.items():
        setattr(response, field, value)
    db.commit()
    db.refresh(response)
    return response


def deactivate_response(db: Session, response: CannedResponse) -> CannedResponse:
    return update_response(db, response, CannedResponseUpdate(is_active=False))
