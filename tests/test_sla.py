from datetime import datetime, timedelta, timezone

import pytest

from app.models import Priority, TicketStatus
from app.services.sla import calculate_sla_deadline, is_overdue

CREATED = datetime(2026, 1, 10, 9, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("priority", "hours"),
    [(Priority.CRITICA, 4), (Priority.ALTA, 8), (Priority.MEDIA, 24), (Priority.BAIXA, 72)],
)
def test_prazo_por_prioridade(priority: Priority, hours: int):
    assert calculate_sla_deadline(CREATED, priority) == CREATED + timedelta(hours=hours)


def test_atrasado_quando_passou_do_prazo_e_esta_aberto():
    deadline = calculate_sla_deadline(CREATED, Priority.CRITICA)
    assert is_overdue(deadline, TicketStatus.EM_ANDAMENTO, now=deadline + timedelta(minutes=1))
    assert not is_overdue(deadline, TicketStatus.EM_ANDAMENTO, now=deadline - timedelta(minutes=1))


@pytest.mark.parametrize("status", [TicketStatus.RESOLVIDO, TicketStatus.FECHADO])
def test_resolvido_ou_fechado_nunca_fica_atrasado(status: TicketStatus):
    deadline = calculate_sla_deadline(CREATED, Priority.CRITICA)
    assert not is_overdue(deadline, status, now=deadline + timedelta(days=30))
