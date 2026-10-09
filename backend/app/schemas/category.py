from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=60)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]


class CategoryCreate(BaseModel):
    name: Name
    description: Description | None = None


class CategoryUpdate(BaseModel):
    """Só os campos enviados são alterados. `is_active: true` reativa a categoria."""

    name: Name | None = None
    description: Description | None = None
    is_active: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    is_active: bool
    created_at: datetime
