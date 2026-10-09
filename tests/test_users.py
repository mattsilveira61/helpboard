import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import Role, User
from conftest import auth_header, create_user

NEW_USER = {"name": "Paula Nova", "email": "Paula@Teste.dev", "password": "senha-forte-123", "role": "TECNICO"}


# --- Acesso por perfil ---


@pytest.mark.parametrize("profile", ["tecnico", "solicitante"])
@pytest.mark.parametrize(
    ("method", "url"),
    [("get", "/users"), ("post", "/users"), ("get", "/users/1"), ("patch", "/users/1"), ("delete", "/users/1")],
)
def test_somente_admin_gerencia_usuarios(client: TestClient, request, profile: str, method: str, url: str):
    user = request.getfixturevalue(profile)

    response = client.request(method, url, headers=auth_header(user), json=NEW_USER)

    assert response.status_code == 403


def test_gerenciar_usuarios_exige_login(client: TestClient):
    assert client.get("/users").status_code == 401


# --- CRUD pelo admin ---


def test_admin_cria_usuario(client: TestClient, db: Session, admin: User):
    response = client.post("/users", headers=auth_header(admin), json=NEW_USER)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "paula@teste.dev"  # normalizado para minúsculas
    assert body["role"] == "TECNICO"
    assert body["is_active"] is True
    assert "password" not in body and "password_hash" not in body

    created = db.get(User, body["id"])
    assert verify_password(NEW_USER["password"], created.password_hash)


def test_nao_cria_usuario_com_email_repetido(client: TestClient, admin: User):
    client.post("/users", headers=auth_header(admin), json=NEW_USER)

    response = client.post("/users", headers=auth_header(admin), json=NEW_USER | {"email": "PAULA@teste.dev"})

    assert response.status_code == 409


@pytest.mark.parametrize(
    "invalid",
    [
        {"email": "nao-e-email"},
        {"password": "curta"},
        {"password": "ç" * 40},  # 80 bytes: passa do limite do bcrypt
        {"role": "SUPERADMIN"},
        {"name": " "},
    ],
)
def test_valida_dados_do_novo_usuario(client: TestClient, admin: User, invalid: dict):
    response = client.post("/users", headers=auth_header(admin), json=NEW_USER | invalid)
    assert response.status_code == 422


def test_admin_lista_usuarios_com_filtros(client: TestClient, db: Session, admin: User, tecnico: User):
    create_user(db, Role.TECNICO, "inativo@teste.dev", is_active=False)
    headers = auth_header(admin)

    todos = client.get("/users", headers=headers).json()
    tecnicos_ativos = client.get("/users", headers=headers, params={"role": "TECNICO", "active": True}).json()

    assert len(todos) == 3
    assert [u["email"] for u in tecnicos_ativos] == [tecnico.email]


def test_admin_edita_usuario_parcialmente(client: TestClient, admin: User, tecnico: User):
    response = client.patch(f"/users/{tecnico.id}", headers=auth_header(admin), json={"name": "Novo Nome"})

    assert response.status_code == 200
    assert response.json()["name"] == "Novo Nome"
    assert response.json()["email"] == tecnico.email


def test_admin_troca_a_senha_de_um_usuario(client: TestClient, admin: User, tecnico: User):
    client.patch(f"/users/{tecnico.id}", headers=auth_header(admin), json={"password": "outra-senha-456"})

    response = client.post("/auth/login", json={"email": tecnico.email, "password": "outra-senha-456"})

    assert response.status_code == 200


def test_nao_troca_para_email_de_outro_usuario(client: TestClient, admin: User, tecnico: User):
    response = client.patch(f"/users/{tecnico.id}", headers=auth_header(admin), json={"email": admin.email})
    assert response.status_code == 409


def test_usuario_inexistente(client: TestClient, admin: User):
    assert client.get("/users/999999", headers=auth_header(admin)).status_code == 404


# --- Desativação (Regras 9 e 13) ---


def test_delete_desativa_em_vez_de_apagar(client: TestClient, db: Session, admin: User, tecnico: User):
    response = client.delete(f"/users/{tecnico.id}", headers=auth_header(admin))

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert db.get(User, tecnico.id) is not None


def test_admin_reativa_usuario(client: TestClient, db: Session, admin: User):
    inativo = create_user(db, Role.SOLICITANTE, is_active=False)

    response = client.patch(f"/users/{inativo.id}", headers=auth_header(admin), json={"is_active": True})

    assert response.json()["is_active"] is True


def test_admin_nao_desativa_a_si_mesmo(client: TestClient, admin: User):
    response = client.delete(f"/users/{admin.id}", headers=auth_header(admin))

    assert response.status_code == 409
    assert "próprio" in response.json()["detail"]


def test_admin_nao_tira_o_proprio_perfil_de_admin(client: TestClient, admin: User):
    response = client.patch(f"/users/{admin.id}", headers=auth_header(admin), json={"role": "TECNICO"})
    assert response.status_code == 409


def test_admin_pode_desativar_outro_admin(client: TestClient, db: Session, admin: User):
    outro_admin = create_user(db, Role.ADMIN, "admin2@teste.dev")

    response = client.delete(f"/users/{outro_admin.id}", headers=auth_header(admin))

    assert response.status_code == 200
