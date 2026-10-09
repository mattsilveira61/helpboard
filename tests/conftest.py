from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"


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
