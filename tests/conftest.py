from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import Category, Role, TicketHistory, User

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
# Senha de todos os usuários criados pelos testes
PASSWORD = "senha-forte-123"


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine, None, None]:
    """Banco de testes recriado do zero pelas migrations (testa as migrations também)."""
    url = get_settings().test_database_url
    if not url:
        pytest.fail("Defina TEST_DATABASE_URL no .env para rodar os testes de banco.")

    alembic_cfg = Config(BACKEND_DIR / "alembic.ini")
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    alembic_cfg.attributes["db_url"] = url
    command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")

    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def db(db_engine: Engine) -> Generator[Session, None, None]:
    """Sessão dentro de uma transação que é desfeita no fim de cada teste: um teste não suja o outro."""
    with db_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """Cliente HTTP da API usando a mesma sessão do teste (os dados criados no teste aparecem na API)."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_user(db: Session, role: Role, email: str | None = None, *, is_active: bool = True) -> User:
    user = User(
        name=f"Usuário {role.value.title()}",
        email=email or f"{role.value.lower()}@teste.dev",
        password_hash=hash_password(PASSWORD),
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.flush()
    return user


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id)}"}


@pytest.fixture
def admin(db: Session) -> User:
    return create_user(db, Role.ADMIN)


@pytest.fixture
def tecnico(db: Session) -> User:
    return create_user(db, Role.TECNICO)


@pytest.fixture
def solicitante(db: Session) -> User:
    return create_user(db, Role.SOLICITANTE)


# --- Chamados ---


def open_ticket(client: TestClient, user: User, category: Category, **data) -> dict:
    payload = {"title": "Impressora quebrada", "description": "Não imprime.", "category_id": category.id,
               "priority": "MEDIA"} | data
    response = client.post("/tickets", headers=auth_header(user), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def change_status(client: TestClient, user: User, ticket_id: int, status: str, **extra):
    return client.post(f"/tickets/{ticket_id}/status", headers=auth_header(user), json={"status": status} | extra)


def assume(client: TestClient, user: User, ticket_id: int):
    return client.post(f"/tickets/{ticket_id}/assume", headers=auth_header(user))


def history_actions(db: Session, ticket_id: int) -> list[str]:
    query = select(TicketHistory.action).where(TicketHistory.ticket_id == ticket_id).order_by(TicketHistory.id)
    return list(db.scalars(query))


@pytest.fixture
def category(db: Session) -> Category:
    category = Category(name="Hardware")
    db.add(category)
    db.flush()
    return category


@pytest.fixture
def em_andamento(client: TestClient, solicitante: User, tecnico: User, category: Category) -> dict:
    """Chamado do solicitante, assumido pelo técnico e em atendimento."""
    ticket = open_ticket(client, solicitante, category)
    assume(client, tecnico, ticket["id"])
    return change_status(client, tecnico, ticket["id"], "EM_ANDAMENTO").json()


@pytest.fixture
def resolvido(client: TestClient, tecnico: User, em_andamento: dict) -> dict:
    return change_status(client, tecnico, em_andamento["id"], "RESOLVIDO", solution="Toner trocado.").json()


@pytest.fixture
def fechado(client: TestClient, solicitante: User, resolvido: dict) -> dict:
    return change_status(client, solicitante, resolvido["id"], "FECHADO").json()
