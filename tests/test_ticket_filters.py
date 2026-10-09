from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Category, Role, Ticket, User
from conftest import assume, auth_header, change_status, create_user, open_ticket

SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def search(client: TestClient, user: User, **params) -> dict:
    response = client.get("/tickets", headers=auth_header(user), params=params)
    assert response.status_code == 200, response.text
    return response.json()


def ids(page: dict) -> set[int]:
    return {t["id"] for t in page["items"]}


@pytest.fixture
def cenario(client: TestClient, db: Session, admin: User, solicitante: User, tecnico: User, category: Category) -> dict:
    """Quatro chamados com status, prioridades, categorias, responsáveis e solicitantes diferentes."""
    rede = Category(name="Rede")
    db.add(rede)
    outro_solicitante = create_user(db, Role.SOLICITANTE, "outro@teste.dev")

    impressora = open_ticket(client, solicitante, category, title="Impressora sem toner", priority="ALTA")
    vpn = open_ticket(client, solicitante, rede, title="VPN caindo", description="Desconecta 100% das vezes",
                      priority="CRITICA")
    monitor = open_ticket(client, outro_solicitante, category, title="Monitor piscando", priority="BAIXA")
    wifi = open_ticket(client, outro_solicitante, rede, title="Wi-Fi lento", priority="ALTA")

    assume(client, tecnico, vpn["id"])
    change_status(client, tecnico, vpn["id"], "EM_ANDAMENTO")
    assume(client, tecnico, monitor["id"])
    return {"impressora": impressora["id"], "vpn": vpn["id"], "monitor": monitor["id"], "wifi": wifi["id"],
            "rede": rede.id, "outro_solicitante": outro_solicitante.id}


def test_filtra_por_status(client: TestClient, admin: User, cenario: dict):
    assert ids(search(client, admin, status="EM_ANDAMENTO")) == {cenario["vpn"]}
    assert len(ids(search(client, admin, status=["ABERTO", "EM_ANDAMENTO"]))) == 4


def test_filtra_por_prioridade(client: TestClient, admin: User, cenario: dict):
    assert ids(search(client, admin, priority="ALTA")) == {cenario["impressora"], cenario["wifi"]}
    assert ids(search(client, admin, priority=["CRITICA", "BAIXA"])) == {cenario["vpn"], cenario["monitor"]}


def test_filtra_por_categoria(client: TestClient, admin: User, cenario: dict):
    assert ids(search(client, admin, category_id=cenario["rede"])) == {cenario["vpn"], cenario["wifi"]}


def test_filtra_por_responsavel_e_sem_responsavel(client: TestClient, admin: User, tecnico: User, cenario: dict):
    assert ids(search(client, admin, assigned_to_id=tecnico.id)) == {cenario["vpn"], cenario["monitor"]}
    assert ids(search(client, admin, unassigned=True)) == {cenario["impressora"], cenario["wifi"]}


def test_filtra_por_solicitante(client: TestClient, admin: User, cenario: dict):
    page = search(client, admin, requester_id=cenario["outro_solicitante"])

    assert ids(page) == {cenario["monitor"], cenario["wifi"]}


def test_busca_por_palavra_chave_no_titulo_e_na_descricao(client: TestClient, admin: User, cenario: dict):
    assert ids(search(client, admin, q="impressora")) == {cenario["impressora"]}  # sem diferenciar maiúsculas
    assert ids(search(client, admin, q="desconecta")) == {cenario["vpn"]}  # na descrição
    assert ids(search(client, admin, q="nada disso")) == set()


def test_busca_trata_curingas_como_texto(client: TestClient, admin: User, cenario: dict):
    assert ids(search(client, admin, q="100%")) == {cenario["vpn"]}
    assert ids(search(client, admin, q="%")) == {cenario["vpn"]}
    assert ids(search(client, admin, q="_")) == set()


def test_busca_pelo_id(client: TestClient, admin: User, cenario: dict):
    assert cenario["wifi"] in ids(search(client, admin, q=str(cenario["wifi"])))
    assert cenario["wifi"] in ids(search(client, admin, q=f"#{cenario['wifi']}"))
    assert search(client, admin, q="99999999999")["total"] == 0  # número gigante não quebra a busca


def test_filtros_se_combinam(client: TestClient, admin: User, cenario: dict):
    page = search(client, admin, category_id=cenario["rede"], priority="ALTA", status="ABERTO")

    assert ids(page) == {cenario["wifi"]}


def test_filtros_respeitam_a_visibilidade(client: TestClient, solicitante: User, cenario: dict):
    # O solicitante pede os chamados de outra pessoa: o filtro não fura a regra de visibilidade
    assert search(client, solicitante, requester_id=cenario["outro_solicitante"])["total"] == 0
    assert ids(search(client, solicitante, category_id=cenario["rede"])) == {cenario["vpn"]}


def test_filtra_por_periodo_no_fuso_da_empresa(client: TestClient, db: Session, admin: User, cenario: dict):
    def set_created(ticket_id: int, moment: datetime):
        db.get(Ticket, ticket_id).created_at = moment

    # 23h de 01/03 em São Paulo já é 02/03 em UTC: deve contar como dia 01/03
    set_created(cenario["impressora"], datetime(2026, 3, 1, 23, 0, tzinfo=SAO_PAULO))
    set_created(cenario["vpn"], datetime(2026, 3, 2, 0, 30, tzinfo=SAO_PAULO))
    set_created(cenario["monitor"], datetime(2026, 3, 5, 12, 0, tzinfo=SAO_PAULO))
    set_created(cenario["wifi"], datetime(2026, 4, 1, 9, 0, tzinfo=SAO_PAULO))
    db.flush()

    assert ids(search(client, admin, created_from="2026-03-01", created_to="2026-03-01")) == {cenario["impressora"]}
    assert ids(search(client, admin, created_from="2026-03-02", created_to="2026-03-05")) == {
        cenario["vpn"], cenario["monitor"]
    }
    assert ids(search(client, admin, created_from="2026-03-10")) == {cenario["wifi"]}
    assert ids(search(client, admin, created_to="2026-03-01")) == {cenario["impressora"]}


def test_periodo_invertido_e_recusado(client: TestClient, admin: User):
    response = client.get("/tickets?created_from=2026-03-10&created_to=2026-03-01", headers=auth_header(admin))

    assert response.status_code == 422


@pytest.mark.parametrize("params", ["status=PERDIDO", "priority=URGENTE", "page=0", "page_size=101", "created_from=ontem"])
def test_parametros_invalidos_sao_recusados(client: TestClient, admin: User, params: str):
    assert client.get(f"/tickets?{params}", headers=auth_header(admin)).status_code == 422


# --- Paginação ---


def test_paginacao(client: TestClient, admin: User, solicitante: User, category: Category):
    created = [open_ticket(client, solicitante, category, title=f"Chamado {n}")["id"] for n in range(5)]

    first = search(client, admin, page_size=2)
    last = search(client, admin, page_size=2, page=3)
    beyond = search(client, admin, page_size=2, page=4)

    assert (first["total"], first["pages"], first["page"], first["page_size"]) == (5, 3, 1, 2)
    assert [t["id"] for t in first["items"]] == created[:2]
    assert [t["id"] for t in last["items"]] == created[4:]
    assert beyond["items"] == [] and beyond["total"] == 5


def test_lista_vazia(client: TestClient, admin: User):
    page = search(client, admin)

    assert (page["items"], page["total"], page["pages"]) == ([], 0, 0)
