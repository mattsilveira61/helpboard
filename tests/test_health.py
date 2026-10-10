import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


def test_health_retorna_ok_com_banco_conectado(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_erro_inesperado_responde_500_generico_com_cors(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
):
    def broken_execute(*args, **kwargs):
        raise RuntimeError("senha=segredo no meio do traceback")

    monkeypatch.setattr(db, "execute", broken_execute)

    response = client.get("/health", headers={"Origin": "http://localhost:5500"})

    assert response.status_code == 500
    assert response.json() == {"detail": "Erro interno no servidor. Tente de novo mais tarde."}
    assert "segredo" not in response.text
    assert response.headers["access-control-allow-origin"] == "http://localhost:5500"
