from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field, model_validator

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


class TicketFilters(BaseModel):
    """Filtros da listagem (query string). Todos são combinados com E, e sempre dentro do que o perfil pode ver."""

    status: list[TicketStatus] = Field(default=[], description="Um ou mais status (repita o parâmetro)")
    priority: list[Priority] = Field(default=[], description="Uma ou mais prioridades (repita o parâmetro)")
    category_id: int | None = None
    assigned_to_id: int | None = None
    unassigned: bool = Field(default=False, description="Só os chamados sem responsável")
    requester_id: int | None = None
    created_from: date | None = Field(default=None, description="Abertos a partir deste dia (inclusive)")
    created_to: date | None = Field(default=None, description="Abertos até este dia (inclusive)")
    q: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] | None = Field(
        default=None, description="Palavra-chave no título ou na descrição. Um número (ou #número) busca também pelo ID"
    )
    include_archived: bool = Field(default=False, description="Incluir arquivados (só tem efeito para o admin)")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def _check_period(self):
        if self.created_from and self.created_to and self.created_from > self.created_to:
            raise ValueError("created_from não pode ser depois de created_to.")
        return self


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
