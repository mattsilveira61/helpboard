from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Ticket, TicketStatus, User
from app.services.tickets import auto_close_stale
from conftest import auth_header, history_actions


def age(db: Session, ticket_id: int, days: float) -> Ticket:
    """Faz de conta que a solução foi registrada há `days` dias."""
    ticket = db.get(Ticket, ticket_id)
    ticket.resolved_at -= timedelta(days=days)
    db.flush()
    return ticket


@pytest.fixture
def auto_close_days(monkeypatch):
    def set_days(days: int):
        monkeypatch.setattr(get_settings(), "auto_close_days", days)

    set_days(7)
    return set_days


def test_resolvido_ha_mais_de_7_dias_fecha_sozinho(
    client: TestClient, db: Session, solicitante: User, tecnico: User, resolvido: dict, auto_close_days
):
    ticket = age(db, resolvido["id"], 8)
    resolved_at = ticket.resolved_at

    body = client.get(f"/tickets/{resolvido['id']}", headers=auth_header(solicitante)).json()

    assert body["status"] == "FECHADO"
    db.refresh(ticket)
    assert ticket.closed_at == resolved_at + timedelta(days=7)  # na data em que o prazo venceu
    history = client.get(f"/tickets/{resolvido['id']}/history", headers=auth_header(solicitante)).json()
    entry = next(h for h in history if h["action"] == "FECHADO_AUTOMATICAMENTE")
    assert entry["user"]["id"] == tecnico.id
    assert entry["created_at"] == body["closed_at"]  # o histórico também fica na data do fechamento


def test_resolvido_recente_continua_aguardando(
    client: TestClient, db: Session, solicitante: User, resolvido: dict, auto_close_days
):
    age(db, resolvido["id"], 6)
    assert client.get(f"/tickets/{resolvido['id']}", headers=auth_header(solicitante)).json()["status"] == "RESOLVIDO"


def test_lista_e_dashboard_tambem_disparam_a_varredura(
    client: TestClient, db: Session, admin: User, resolvido: dict, auto_close_days
):
    ticket = age(db, resolvido["id"], 10)
    client.get("/tickets", headers=auth_header(admin))
    db.refresh(ticket)
    assert ticket.status == TicketStatus.FECHADO

    # Já fechado: não fecha de novo nem duplica o histórico
    client.get("/dashboard", headers=auth_header(admin))
    assert history_actions(db, resolvido["id"]).count("FECHADO_AUTOMATICAMENTE") == 1


def test_arquivado_nao_e_fechado(client: TestClient, db: Session, admin: User, resolvido: dict, auto_close_days):
    client.delete(f"/tickets/{resolvido['id']}", headers=auth_header(admin))
    ticket = age(db, resolvido["id"], 30)
    assert auto_close_stale(db) == 0
    assert ticket.status == TicketStatus.RESOLVIDO


def test_zero_desliga_o_fechamento_automatico(db: Session, resolvido: dict, auto_close_days):
    auto_close_days(0)
    age(db, resolvido["id"], 30)
    assert auto_close_stale(db) == 0


def test_fechado_automaticamente_pode_ser_avaliado(
    client: TestClient, db: Session, solicitante: User, resolvido: dict, auto_close_days
):
    age(db, resolvido["id"], 8)
    response = client.post(f"/tickets/{resolvido['id']}/rating", headers=auth_header(solicitante), json={"rating": 3})
    assert response.status_code == 200
