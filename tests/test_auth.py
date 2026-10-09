from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.models import Role, User
from conftest import PASSWORD, auth_header, create_user


def login(client: TestClient, email: str, password: str = PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_login_retorna_token_e_dados_do_usuario(client: TestClient, tecnico: User):
    response = login(client, tecnico.email)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == tecnico.email
    assert body["user"]["role"] == "TECNICO"
    assert "password_hash" not in body["user"]


def test_token_do_login_funciona_nas_rotas_protegidas(client: TestClient, solicitante: User):
    token = login(client, solicitante.email).json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["id"] == solicitante.id


def test_login_ignora_maiusculas_no_email(client: TestClient, admin: User):
    assert login(client, admin.email.upper()).status_code == 200


def test_login_com_senha_errada(client: TestClient, admin: User):
    response = login(client, admin.email, "senha-errada")

    assert response.status_code == 401
    assert response.json()["detail"] == "E-mail ou senha inválidos."


def test_login_com_email_inexistente_tem_a_mesma_mensagem(client: TestClient):
    response = login(client, "ninguem@teste.dev")

    assert response.status_code == 401
    assert response.json()["detail"] == "E-mail ou senha inválidos."


def test_usuario_desativado_nao_loga(client: TestClient, db: Session):
    user = create_user(db, Role.TECNICO, is_active=False)

    response = login(client, user.email)

    assert response.status_code == 403
    assert "desativado" in response.json()["detail"]


def test_rota_protegida_sem_token(client: TestClient):
    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("token", ["abc.def.ghi", "nao-e-um-jwt", ""])
def test_rota_protegida_com_token_invalido(client: TestClient, token: str):
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


def test_rota_protegida_com_token_vencido(client: TestClient, admin: User):
    token = create_access_token(admin.id, expires_delta=timedelta(minutes=-1))

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401


def test_token_adulterado_e_recusado(client: TestClient, admin: User):
    header, payload, signature = create_access_token(admin.id).split(".")
    tampered = f"{header}.{payload}.{signature[:-2]}xx"

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})

    assert response.status_code == 401


def test_usuario_desativado_depois_do_login_perde_o_acesso(client: TestClient, db: Session, tecnico: User):
    headers = auth_header(tecnico)
    assert client.get("/auth/me", headers=headers).status_code == 200

    tecnico.is_active = False
    db.flush()

    assert client.get("/auth/me", headers=headers).status_code == 401
