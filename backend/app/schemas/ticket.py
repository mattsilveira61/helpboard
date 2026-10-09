from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, computed_field

from app.models import Priority, TicketStatus
from app.services.sla import is_overdue

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120)]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TicketCreate(BaseModel):
    """Não tem requester_id nem status: o solicitante é sempre quem está logado e o status começa ABERTO."""

    title: Title
    description: Text
    category_id: int
    priority: Priority


class TicketUpdate(BaseModel):
    """Só os campos enviados são alterados. O que cada perfil pode mudar está na matriz de permissões."""

    title: Title | None = None
    description: Text | None = None
    category_id: int | None = None
    priority: Priority | None = None


class AssigneeUpdate(BaseModel):
    """`null` remove o responsável (só com o chamado em ABERTO)."""

    assigned_to_id: int | None


class StatusChange(BaseModel):
    status: TicketStatus
    # Obrigatória para ir para RESOLVIDO (se o chamado ainda não tiver solução registrada)
    solution: Text | None = None
    # Obrigatório para recusar a solução (RESOLVIDO → EM_ANDAMENTO) e para reabrir (FECHADO → ABERTO)
    reason: Text | None = None


class UserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class CategorySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: TicketStatus
    priority: Priority
    category: CategorySummary
    requester: UserSummary
    assigned_to: UserSummary | None
    sla_deadline: datetime
    solution: str | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    closed_at: datetime | None

    @computed_field
    @property
    def is_overdue(self) -> bool:
        return is_overdue(self.sla_deadline, self.status)
