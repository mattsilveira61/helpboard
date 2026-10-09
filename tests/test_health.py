from fastapi.testclient import TestClient


def test_health_retorna_ok_com_banco_conectado(client: TestClient):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
