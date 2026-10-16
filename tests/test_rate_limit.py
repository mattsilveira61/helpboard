import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import LoginLimiter, login_limiter
from app.models import User
from conftest import PASSWORD


def login(client: TestClient, email: str, password: str):
    return client.post("/auth/login", json={"email": email, "password": password})

class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

@pytest.fixture
def clock(monkeypatch) -> FakeClock:
    fake = FakeClock()
    monkeypatch.setattr(login_limiter, "clock", fake)
    return fake

def test_quinto_erro_bloqueia_ate_a_senha_certa(client: TestClient, tecnico: User, clock: FakeClock):
    for _ in range(5):
        assert login(client, tecnico.email, "errada").status_code == 401

    response = login(client, tecnico.email, PASSWORD)
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "60"
    assert "Muitas tentativas" in response.json()["detail"]

def test_bloqueio_acaba_quando_a_janela_passa(client: TestClient, tecnico: User, clock: FakeClock):
    for _ in range(5):
        login(client, tecnico.email, "errada")
        clock.now += 10

    # O primeiro erro foi há 50 s: faltam 10 s
    assert login(client, tecnico.email, PASSWORD).headers["Retry-After"] == "10"
    clock.now += 10
    assert login(client, tecnico.email, PASSWORD).status_code == 200

def test_acerto_zera_o_contador(client: TestClient, tecnico: User, clock: FakeClock):
    for _ in range(4):
        login(client, tecnico.email, "errada")
    assert login(client, tecnico.email, PASSWORD).status_code == 200

    for _ in range(4):
        assert login(client, tecnico.email, "errada").status_code == 401

def test_bloqueio_vale_so_para_aquele_email(client: TestClient, tecnico: User, admin: User, clock: FakeClock):
    for _ in range(5):
        login(client, tecnico.email.upper(), "errada")

    assert login(client, tecnico.email, PASSWORD).status_code == 429  # maiúsculas não escapam do limite
    assert login(client, admin.email, PASSWORD).status_code == 200

def test_email_inexistente_tambem_e_limitado(client: TestClient, clock: FakeClock):
    for _ in range(5):
        login(client, "ninguem@helpboard.dev", "x")
    assert login(client, "ninguem@helpboard.dev", "x").status_code == 429

def test_limiter_separa_por_ip():
    clock = FakeClock()
    limiter = LoginLimiter(max_failures=2, window_seconds=60, clock=clock)
    limiter.fail("1.1.1.1", "a@x.dev")
    limiter.fail("1.1.1.1", "a@x.dev")

    assert limiter.retry_after("1.1.1.1", "a@x.dev") == 60
    assert limiter.retry_after("2.2.2.2", "a@x.dev") == 0
