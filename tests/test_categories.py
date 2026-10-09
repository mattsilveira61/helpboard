import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Category, Ticket, User
from conftest import auth_header, open_ticket


@pytest.fixture
def inativa(db: Session) -> Category:
    category = Category(name="Antiga", is_active=False)
    db.add(category)
    db.flush()
    return category


def names(response) -> list[str]:
    return [c["name"] for c in response.json()]


# --- Leitura ---


@pytest.mark.parametrize("profile", ["admin", "tecnico", "solicitante"])
def test_todos_listam_so_as_ativas_em_ordem_alfabetica(
    client: TestClient, db: Session, request, category: Category, inativa: Category, profile: str
):
    db.add(Category(name="Acesso"))
    db.flush()

    response = client.get("/categories", headers=auth_header(request.getfixturevalue(profile)))

    assert response.status_code == 200
    assert names(response) == ["Acesso", "Hardware"]


def test_so_admin_ve_as_inativas(
    client: TestClient, admin: User, solicitante: User, category: Category, inativa: Category
):
    url = "/categories?include_inactive=true"

    assert names(client.get(url, headers=auth_header(admin))) == ["Antiga", "Hardware"]
    assert names(client.get(url, headers=auth_header(solicitante))) == ["Hardware"]


def test_categorias_exigem_login(client: TestClient):
    assert client.get("/categories").status_code == 401


def test_detalha_categoria(client: TestClient, solicitante: User, category: Category):
    assert client.get(f"/categories/{category.id}", headers=auth_header(solicitante)).json()["name"] == "Hardware"
    assert client.get("/categories/999999", headers=auth_header(solicitante)).status_code == 404


# --- Gerenciamento (só admin) ---


@pytest.mark.parametrize("profile", ["tecnico", "solicitante"])
@pytest.mark.parametrize(("method", "url"), [("post", "/categories"), ("patch", "/categories/1"), ("delete", "/categories/1")])
def test_so_admin_gerencia_categorias(client: TestClient, request, profile: str, method: str, url: str):
    response = client.request(method, url, headers=auth_header(request.getfixturevalue(profile)), json={"name": "Nova"})

    assert response.status_code == 403


def test_admin_cria_categoria(client: TestClient, admin: User):
    response = client.post(
        "/categories", headers=auth_header(admin), json={"name": "  Telefonia ", "description": "Ramais e celulares"}
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["name"], body["description"], body["is_active"]) == ("Telefonia", "Ramais e celulares", True)


@pytest.mark.parametrize("name", ["Hardware", "hardware", "HARDWARE"])
def test_nome_de_categoria_e_unico(client: TestClient, admin: User, category: Category, name: str):
    assert client.post("/categories", headers=auth_header(admin), json={"name": name}).status_code == 409


@pytest.mark.parametrize("name", ["", "x", "x" * 61])
def test_nome_precisa_ter_de_2_a_60_caracteres(client: TestClient, admin: User, name: str):
    assert client.post("/categories", headers=auth_header(admin), json={"name": name}).status_code == 422


def test_admin_edita_categoria(client: TestClient, db: Session, admin: User, category: Category):
    db.add(Category(name="Rede"))
    db.flush()
    url = f"/categories/{category.id}"

    assert client.patch(url, headers=auth_header(admin), json={"name": "rede"}).status_code == 409
    response = client.patch(url, headers=auth_header(admin), json={"name": "Hardware e periféricos"})

    assert response.status_code == 200
    assert response.json()["name"] == "Hardware e periféricos"
    # Mudar só a caixa do próprio nome não é conflito
    assert client.patch(url, headers=auth_header(admin), json={"name": "HARDWARE E PERIFÉRICOS"}).status_code == 200


def test_desativar_categoria_mantem_os_chamados_antigos(
    client: TestClient, db: Session, admin: User, solicitante: User, category: Category
):
    ticket = open_ticket(client, solicitante, category)

    response = client.delete(f"/categories/{category.id}", headers=auth_header(admin))

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    # Some do formulário...
    assert names(client.get("/categories", headers=auth_header(solicitante))) == []
    # ...não aceita chamados novos...
    payload = {"title": "Outro", "description": "x", "category_id": category.id, "priority": "BAIXA"}
    assert client.post("/tickets", headers=auth_header(solicitante), json=payload).status_code == 409
    # ...mas o chamado antigo continua com ela
    detail = client.get(f"/tickets/{ticket['id']}", headers=auth_header(solicitante)).json()
    assert detail["category"]["name"] == "Hardware"
    assert db.get(Ticket, ticket["id"]).category_id == category.id


def test_admin_reativa_categoria(client: TestClient, admin: User, inativa: Category):
    response = client.patch(f"/categories/{inativa.id}", headers=auth_header(admin), json={"is_active": True})

    assert response.json()["is_active"] is True
