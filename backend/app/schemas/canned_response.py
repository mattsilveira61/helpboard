from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]


class CannedResponseCreate(BaseModel):
    title: Title
    body: Body


class CannedResponseUpdate(BaseModel):
    """Só os campos enviados são alterados. `is_active: true` reativa a resposta."""

    title: Title | None = None
    body: Body | None = None
    is_active: bool | None = None


class CannedResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    is_active: bool
    created_at: datetime
