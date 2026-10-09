from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core import clock
from app.models import Category, Role, Ticket, User
from conftest import assume, auth_header, change_status, create_user, open_ticket

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
MARCO = {"start": "2026-03-01", "end": "2026-03-31"}


def dashboard(client: TestClient, user: User, **params) -> dict:
    response = client.get("/dashboard", headers=auth_header(user), params=params)
    assert response.status_code == 200, response.text
    return response.json()


def resolve(client: TestClient, tecnico: User, ticket_id: int) -> None:
    assume(client, tecnico, ticket_id)
    change_status(client, tecnico, ticket_id, "EM_ANDAMENTO")
    change_status(client, tecnico, ticket_id, "RESOLVIDO", solution="Feito.")


def set_dates(db: Session, ticket_id: int, created: datetime, resolved: datetime | None = None) -> None:
    ticket = db.get(Ticket, ticket_id)
    ticket.created_at = created
    if resolved:
        ticket.resolved_at = resolved
    db.flush()


def em_marco(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 3, day, hour, tzinfo=SAO_PAULO)


# --- Acesso ---


def test_dashboard_exige_login(client: TestClient):
    assert client.get("/dashboard").status_code == 401


def test_solicitante_nao_acessa_o_dashboard(client: TestClient, solicitante: User):
    assert client.get("/dashboard", headers=auth_header(solicitante)).status_code == 403


# --- Período ---


def test_periodo_padrao_sao_os_ultimos_30_dias(client: TestClient, admin: User, category: Category):
    body = dashboard(client, admin)

    today = clock.today()
    assert body["scope"] == "TODOS"
    assert body["period"] == {"start": str(today - timedelta(days=29)), "end": str(today)}
    assert len(body["timeline"]) == 30
    assert body["timeline"][-1]["day"] == str(today)


def test_dashboard_vazio_vem_zerado(client: TestClient, admin: User, category: Category):
    body = dashboard(client, admin, **MARCO)

    assert body["backlog"] == {"open": 0, "in_progress": 0, "critical": 0, "overdue": 0, "unassigned": 0}
    assert body["created"]["total"] == 0
    assert set(body["created"]["by_status"].values()) == {0}
    assert body["created"]["by_category"] == [{"id": category.id, "name": "Hardware", "total": 0}]
    assert body["resolved"] == {"total": 0, "avg_resolution_hours": None}
    assert {d["created"] + d["resolved"] for d in body["timeline"]} == {0}


@pytest.mark.parametrize(
    "params",
    ["start=2026-03-10&end=2026-03-01", "start=2025-01-01&end=2026-03-01", "start=ontem", "end=2026-02-30"],
)
def test_periodo_invalido_e_recusado(client: TestClient, admin: User, params: str):
    assert client.get(f"/dashboard?{params}", headers=auth_header(admin)).status_code == 422


# --- Fila atual ---


def test_fila_atual(
    client: TestClient, db: Session, admin: User, solicitante: User, tecnico: User, category: Category
):
    open_ticket(client, solicitante, category, priority="CRITICA")  # disponível: conta em critical e unassigned
    atribuido = open_ticket(client, solicitante, category)
    em_atendimento = open_ticket(client, solicitante, category, priority="CRITICA")
    resolvido = open_ticket(client, solicitante, category, priority="CRITICA")
    assume(client, tecnico, atribuido["id"])
    assume(client, tecnico, em_atendimento["id"])
    change_status(client, tecnico, em_atendimento["id"], "EM_ANDAMENTO")
    resolve(client, tecnico, resolvido["id"])

    # Prazo estourado: conta como atrasado enquanto não for resolvido
    for ticket_id in (atribuido["id"], resolvido["id"]):
        db.get(Ticket, ticket_id).sla_deadline = clock.now() - timedelta(hours=1)
    db.flush()

    backlog = dashboard(client, admin)["backlog"]

    assert backlog == {"open": 2, "in_progress": 1, "critical": 2, "overdue": 1, "unassigned": 1}


def test_arquivados_nao_entram_na_conta(
    client: TestClient, admin: User, solicitante: User, category: Category
):
    ticket = open_ticket(client, solicitante, category)
    client.delete(f"/tickets/{ticket['id']}", headers=auth_header(admin))

    body = dashboard(client, admin)

    assert body["backlog"]["open"] == 0
    assert body["created"]["total"] == 0


# --- Abertos no período ---


def test_abertos_no_periodo_por_status_prioridade_e_categoria(
    client: TestClient, db: Session, admin: User, solicitante: User, tecnico: User, category: Category
):
    rede = Category(name="Rede")
    vazia = Category(name="Vazia")
    antiga = Category(name="Antiga", is_active=False)
    db.add_all([rede, vazia, antiga])
    db.flush()

    a = open_ticket(client, solicitante, rede, priority="ALTA")
    b = open_ticket(client, solicitante, rede, priority="ALTA")
    c = open_ticket(client, solicitante, category, priority="BAIXA")
    fora = open_ticket(client, solicitante, category, priority="CRITICA")
    resolve(client, tecnico, b["id"])
    for ticket_id, day in ((a["id"], 1), (b["id"], 15), (c["id"], 31)):
        set_dates(db, ticket_id, em_marco(day))
    set_dates(db, fora["id"], datetime(2026, 4, 1, 0, 30, tzinfo=SAO_PAULO))

    created = dashboard(client, admin, **MARCO)["created"]

    assert created["total"] == 3
    assert created["by_status"] == {"ABERTO": 2, "EM_ANDAMENTO": 0, "RESOLVIDO": 1, "FECHADO": 0}
    assert created["by_priority"] == {"CRITICA": 0, "ALTA": 2, "MEDIA": 0, "BAIXA": 1}
    # Mais chamados primeiro; categoria ativa sem chamados aparece zerada; inativa sem chamados some
    assert [(c["name"], c["total"]) for c in created["by_category"]] == [("Rede", 2), ("Hardware", 1), ("Vazia", 0)]


def test_dia_segue_o_fuso_da_empresa(
    client: TestClient, db: Session, admin: User, solicitante: User, category: Category
):
    ticket = open_ticket(client, solicitante, category)
    # 23h de 01/03 em São Paulo já é 02/03 em UTC
    set_dates(db, ticket["id"], em_marco(1, hour=23))

    body = dashboard(client, admin, start="2026-03-01", end="2026-03-02")

    assert body["created"]["total"] == 1
    assert body["timeline"] == [
        {"day": "2026-03-01", "created": 1, "resolved": 0},
        {"day": "2026-03-02", "created": 0, "resolved": 0},
    ]


# --- Resolvidos e tempo médio ---


def test_resolvidos_no_periodo_e_tempo_medio(
    client: TestClient, db: Session, admin: User, solicitante: User, tecnico: User, category: Category
):
    rapido = open_ticket(client, solicitante, category)
    lento = open_ticket(client, solicitante, category)
    fechado = open_ticket(client, solicitante, category)
    fora = open_ticket(client, solicitante, category)
    for ticket in (rapido, lento, fechado, fora):
        resolve(client, tecnico, ticket["id"])
    change_status(client, solicitante, fechado["id"], "FECHADO")

    set_dates(db, rapido["id"], em_marco(2, hour=8), resolved=em_marco(2, hour=10))  # 2 h
    set_dates(db, lento["id"], em_marco(1, hour=8), resolved=em_marco(3, hour=8))  # 48 h
    set_dates(db, fechado["id"], em_marco(10, hour=8), resolved=em_marco(10, hour=18))  # 10 h
    # Aberto em fevereiro, resolvido em abril: fora do período nas duas datas
    set_dates(db, fora["id"], datetime(2026, 2, 20, tzinfo=SAO_PAULO), resolved=datetime(2026, 4, 2, tzinfo=SAO_PAULO))

    body = dashboard(client, admin, **MARCO)

    assert body["resolved"] == {"total": 3, "avg_resolution_hours": 20.0}
    timeline = {d["day"]: d for d in body["timeline"]}
    assert (timeline["2026-03-02"]["created"], timeline["2026-03-02"]["resolved"]) == (1, 1)
    assert timeline["2026-03-03"]["resolved"] == 1
    assert timeline["2026-03-10"]["resolved"] == 1


def test_solucao_recusada_nao_conta_como_resolvido(
    client: TestClient, admin: User, solicitante: User, resolvido: dict
):
    change_status(client, solicitante, resolvido["id"], "EM_ANDAMENTO", reason="Não resolveu.")

    assert dashboard(client, admin)["resolved"]["total"] == 0


# --- Por técnico ---


def test_numeros_por_tecnico(
    client: TestClient, db: Session, admin: User, solicitante: User, tecnico: User, category: Category
):
    ocioso = create_user(db, Role.TECNICO, "ocioso@teste.dev")
    create_user(db, Role.TECNICO, "inativo@teste.dev", is_active=False)
    aberto = open_ticket(client, solicitante, category)
    andamento = open_ticket(client, solicitante, category)
    feito = open_ticket(client, solicitante, category)
    do_admin = open_ticket(client, solicitante, category)
    assume(client, tecnico, aberto["id"])
    assume(client, tecnico, andamento["id"])
    change_status(client, tecnico, andamento["id"], "EM_ANDAMENTO")
    resolve(client, tecnico, feito["id"])
    client.put(f"/tickets/{do_admin['id']}/assignee", headers=auth_header(admin), json={"assigned_to_id": admin.id})

    now = datetime.now(timezone.utc)
    set_dates(db, feito["id"], now - timedelta(hours=5), resolved=now)

    rows = {r["id"]: r for r in dashboard(client, admin)["by_assignee"]}

    # Técnico ativo aparece mesmo zerado; o admin aparece porque tem chamado; o técnico inativo sem nada some
    assert set(rows) == {tecnico.id, ocioso.id, admin.id}
    mine = rows[tecnico.id]
    assert (mine["name"], mine["open"], mine["in_progress"], mine["resolved"]) == (tecnico.name, 1, 1, 1)
    assert mine["avg_resolution_hours"] == pytest.approx(5.0, abs=0.1)
    assert (rows[ocioso.id]["open"], rows[ocioso.id]["resolved"], rows[ocioso.id]["avg_resolution_hours"]) == (0, 0, None)
    assert rows[admin.id]["open"] == 1


# --- Escopo do técnico ---


def test_tecnico_ve_so_os_seus_numeros(
    client: TestClient, db: Session, admin: User, solicitante: User, tecnico: User, category: Category
):
    outro = create_user(db, Role.TECNICO, "outro.tecnico@teste.dev")
    meu = open_ticket(client, solicitante, category, priority="CRITICA")
    dele = open_ticket(client, solicitante, category)
    open_ticket(client, solicitante, category)  # disponível
    assume(client, tecnico, meu["id"])
    assume(client, outro, dele["id"])
    resolve(client, outro, dele["id"])

    body = dashboard(client, tecnico)

    assert body["scope"] == "MEUS"
    assert body["backlog"] == {"open": 1, "in_progress": 0, "critical": 1, "overdue": 0, "unassigned": 1}
    assert body["created"]["total"] == 1
    assert body["resolved"]["total"] == 0
    assert [r["id"] for r in body["by_assignee"]] == [tecnico.id]
    # O admin continua vendo tudo
    assert dashboard(client, admin)["created"]["total"] == 3
