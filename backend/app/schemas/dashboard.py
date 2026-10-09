from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.core import clock
from app.models import Priority, TicketStatus

DEFAULT_DAYS = 30
MAX_DAYS = 366


class DashboardParams(BaseModel):
    """Período dos indicadores, em dias do calendário da empresa (inclusivos)."""

    start: date | None = Field(default=None, description=f"Primeiro dia (padrão: {DEFAULT_DAYS} dias até `end`)")
    end: date | None = Field(default=None, description="Último dia (padrão: hoje)")

    @model_validator(mode="after")
    def _fill_period(self):
        self.end = self.end or clock.today()
        self.start = self.start or self.end - timedelta(days=DEFAULT_DAYS - 1)
        if self.start > self.end:
            raise ValueError("start não pode ser depois de end.")
        if (self.end - self.start).days >= MAX_DAYS:
            raise ValueError(f"O período pode ter no máximo {MAX_DAYS} dias.")
        return self


class Period(BaseModel):
    start: date
    end: date


class Backlog(BaseModel):
    """Fila atual, independente do período: chamados abertos ou em andamento."""

    open: int = Field(description="Status ABERTO")
    in_progress: int = Field(description="Status EM_ANDAMENTO")
    critical: int = Field(description="Prioridade CRITICA ainda não resolvidos")
    overdue: int = Field(description="Passaram do prazo (SLA) e ainda não foram resolvidos")
    unassigned: int = Field(description="Abertos sem responsável, disponíveis para os técnicos assumirem")


class CategoryCount(BaseModel):
    id: int
    name: str
    total: int


class CreatedStats(BaseModel):
    """Chamados abertos no período, pelo status e pela prioridade que têm hoje."""

    total: int
    by_status: dict[TicketStatus, int]
    by_priority: dict[Priority, int]
    by_category: list[CategoryCount] = Field(description="Categorias ativas (mesmo com zero) e inativas com chamados")


class ResolvedStats(BaseModel):
    """Chamados resolvidos no período (data da solução), contando os que já foram fechados."""

    total: int
    avg_resolution_hours: float | None = Field(description="Da abertura até a solução; null se não houver nenhum")


class DayCount(BaseModel):
    day: date
    created: int
    resolved: int


class AssigneeStats(BaseModel):
    id: int
    name: str
    open: int = Field(description="Atribuídos a ele com status ABERTO")
    in_progress: int
    resolved: int = Field(description="Resolvidos no período")
    avg_resolution_hours: float | None


class DashboardOut(BaseModel):
    scope: Literal["TODOS", "MEUS"] = Field(
        description="TODOS para o admin; MEUS para o técnico (só os chamados atribuídos a ele)"
    )
    period: Period
    backlog: Backlog
    created: CreatedStats
    resolved: ResolvedStats
    timeline: list[DayCount] = Field(description="Um item por dia do período, inclusive os dias sem movimento")
    by_assignee: list[AssigneeStats] = Field(description="Técnicos ativos (mesmo com zero) e quem tiver chamados")
