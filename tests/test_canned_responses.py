import pytest
from fastapi.testclient import TestClient

from app.models import User
from conftest import auth_header

URL = "/canned-responses"


def create(client: TestClient, admin: User, title: str = "Pedir mais detalhes", body: str = "Pode enviar um print?"):
    return client.post(URL, headers=auth_header(admin), json={"title": title, "body": body})


def test_admin_cria_e_tecnico_lista(client: TestClient, admin: User, tecnico: User):
    response = create(client, admin, "  Reiniciar o computador ", "  Reinicie e teste de novo.  ")
    assert response.status_code == 201
    assert (response.json()["title"], response.json()["body"]) == ("Reiniciar o computador", "Reinicie e teste de novo.")

    items = client.get(URL, headers=auth_header(tecnico)).json()
    assert [i["title"] for i in items] == ["Reiniciar o computador"]


def test_lista_em_ordem_alfabetica_e_sem_inativas(client: TestClient, admin: User, tecnico: User):
    b = create(client, admin, "Bom dia").json()
    create(client, admin, "Aguardando peça")
    client.delete(f"{URL}/{b['id']}", headers=auth_header(admin))

    assert [i["title"] for i in client.get(URL, headers=auth_header(tecnico)).json()] == ["Aguardando peça"]
    # Inativas só para o admin, e só pedindo
    everything = client.get(URL, headers=auth_header(admin), params={"include_inactive": True}).json()
    assert [i["title"] for i in everything] == ["Aguardando peça", "Bom dia"]
    tecnico_pede = client.get(URL, headers=auth_header(tecnico), params={"include_inactive": True}).json()
    assert len(tecnico_pede) == 1


def test_titulo_unico_sem_diferenciar_maiusculas(client: TestClient, admin: User):
    create(client, admin, "Pedir mais detalhes")
    assert create(client, admin, "PEDIR MAIS DETALHES").status_code == 409


def test_editar_e_reativar(client: TestClient, admin: User):
    item = create(client, admin).json()
    client.delete(f"{URL}/{item['id']}", headers=auth_header(admin))

    response = client.patch(f"{URL}/{item['id']}", headers=auth_header(admin), json={"body": "Novo texto", "is_active": True})
    assert response.status_code == 200
    assert (response.json()["body"], response.json()["is_active"]) == ("Novo texto", True)


def test_editar_com_titulo_de_outra_da_409(client: TestClient, admin: User):
    create(client, admin, "Primeira")
    second = create(client, admin, "Segunda").json()
    response = client.patch(f"{URL}/{second['id']}", headers=auth_header(admin), json={"title": "primeira"})
    assert response.status_code == 409


def test_solicitante_nao_acessa(client: TestClient, solicitante: User):
    assert client.get(URL, headers=auth_header(solicitante)).status_code == 403


@pytest.mark.parametrize("method", ["post", "patch", "delete"])
def test_so_admin_gerencia(client: TestClient, admin: User, tecnico: User, method: str):
    item = create(client, admin).json()
    url = URL if method == "post" else f"{URL}/{item['id']}"
    response = client.request(method, url, headers=auth_header(tecnico), json={"title": "Outra", "body": "x"})
    assert response.status_code == 403


@pytest.mark.parametrize("payload", [{"title": "A", "body": "x"}, {"title": "Válido", "body": "   "}])
def test_dados_invalidos(client: TestClient, admin: User, payload: dict):
    assert client.post(URL, headers=auth_header(admin), json=payload).status_code == 422


def test_inexistente_responde_404(client: TestClient, admin: User):
    assert client.patch(f"{URL}/999999", headers=auth_header(admin), json={"body": "x"}).status_code == 404
