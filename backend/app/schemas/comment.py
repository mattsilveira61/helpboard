from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models import HistoryAction
from app.schemas.ticket import UserSummary


class CommentCreate(BaseModel):
    """O autor é sempre o usuário logado. Comentários não são editados nem apagados (Regra 12)."""

    message: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message: str
    user: UserSummary
    created_at: datetime


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action: HistoryAction
    old_value: str | None
    new_value: str | None
    user: UserSummary
    created_at: datetime
