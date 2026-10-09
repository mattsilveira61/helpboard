from datetime import datetime
from enum import StrEnum
from typing import Annotated

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.orm import mapped_column

# Data/hora sempre com fuso (timestamptz), preenchida pelo próprio banco na criação.
CreatedAt = Annotated[
    datetime,
    mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False),
]


def enum_column(enum_cls: type[StrEnum], name: str) -> Enum:
    """Enum guardado como VARCHAR + CHECK (mais fácil de evoluir que o ENUM nativo do Postgres)."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=max(len(m.value) for m in enum_cls),
        values_callable=lambda e: [m.value for m in e],
        validate_strings=True,
    )
