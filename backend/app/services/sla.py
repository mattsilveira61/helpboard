from datetime import datetime, timedelta, timezone

from app.models.enums import Priority, TicketStatus

# Regra 11: prazo em horas corridas a partir da abertura do chamado
SLA_HOURS: dict[Priority, int] = {
    Priority.CRITICA: 4,
    Priority.ALTA: 8,
    Priority.MEDIA: 24,
    Priority.BAIXA: 72,
}


def calculate_sla_deadline(created_at: datetime, priority: Priority) -> datetime:
    return created_at + timedelta(hours=SLA_HOURS[priority])


def is_overdue(
    sla_deadline: datetime, status: TicketStatus, now: datetime | None = None
) -> bool:
    """Atrasado = passou do prazo e ainda não foi resolvido nem fechado."""
    if status in (TicketStatus.RESOLVIDO, TicketStatus.FECHADO):
        return False
    return (now or datetime.now(timezone.utc)) > sla_deadline
