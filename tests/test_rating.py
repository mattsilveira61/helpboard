from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Category, Role, User
from conftest import assume, auth_header, change_status, create_user, history_actions, open_ticket


def rate(client: TestClient, user: User, ticket_id: int, rating: int, comment: str | None = None):
    payload = {"rating": rating} | ({"comment": comment} if comment is not None else {})
    return client.post(f"/tickets/{ticket_id}/rating", headers=auth_header(user), json=payload)

def test_solicitante_avalia_chamado_fechado(client: TestClient, db: Session, solicitante: User, fechado: dict):
    response = rate(client, solicitante, fechado["id"], 5, "  Rápido e resolveu.  ")

    assert response.status_code == 200
    body = response.json()
    assert (body["rating"], body["rating_comment"]) == (5, "Rápido e resolveu.")
    assert body["rated_at"] is not None
    assert history_actions(db, fechado["id"])[-1] == "AVALIADO"

def test_nao_avalia_duas_vezes(client: TestClient, solicitante: User, fechado: dict):
    rate(client, solicitante, fechado["id"], 4)
    response = rate(client, solicitante, fechado["id"], 1)

    assert response.status_code == 409
    assert client.get(f"/tickets/{fechado['id']}", headers=auth_header(solicitante)).json()["rating"] == 4

def test_so_avalia_chamado_fechado(client: TestClient, solicitante: User, resolvido: dict):
    assert rate(client, solicitante, resolvido["id"], 5).status_code == 409

def test_so_quem_abriu_avalia(client: TestClient, tecnico: User, admin: User, fechado: dict):
    assert rate(client, tecnico, fechado["id"], 5).status_code == 403
    assert rate(client, admin, fechado["id"], 5).status_code == 403

def test_chamado_de_outro_solicitante_responde_404(client: TestClient, db: Session, fechado: dict):
    outro = create_user(db, Role.SOLICITANTE, "outro@teste.dev")
    assert rate(client, outro, fechado["id"], 5).status_code == 404

def test_nota_fora_de_1_a_5_e_recusada(client: TestClient, solicitante: User, fechado: dict):
    assert rate(client, solicitante, fechado["id"], 0).status_code == 422
    assert rate(client, solicitante, fechado["id"], 6).status_code == 422
    assert rate(client, solicitante, fechado["id"], 3, "x" * 501).status_code == 422

def test_reabrir_apaga_a_nota_e_permite_nova(client: TestClient, solicitante: User, tecnico: User, fechado: dict):
    tid = fechado["id"]
    rate(client, solicitante, tid, 1, "Não resolveu")
    reaberto = change_status(client, solicitante, tid, "ABERTO", reason="Voltou a falhar").json()
    assert (reaberto["rating"], reaberto["rating_comment"], reaberto["rated_at"]) == (None, None, None)

    assume(client, tecnico, tid)
    change_status(client, tecnico, tid, "EM_ANDAMENTO")
    change_status(client, tecnico, tid, "RESOLVIDO", solution="Peça trocada.")
    change_status(client, solicitante, tid, "FECHADO")
    assert rate(client, solicitante, tid, 5).json()["rating"] == 5

def test_dashboard_mostra_satisfacao_geral_e_por_tecnico(
    client: TestClient, db: Session, admin: User, solicitante: User, tecnico: User, category: Category
):
    for nota in (5, 4, 2):
        ticket = open_ticket(client, solicitante, category)
        assume(client, tecnico, ticket["id"])
        change_status(client, tecnico, ticket["id"], "EM_ANDAMENTO")
        change_status(client, tecnico, ticket["id"], "RESOLVIDO", solution="Feito.")
        change_status(client, solicitante, ticket["id"], "FECHADO")
        rate(client, solicitante, ticket["id"], nota)

    body = client.get("/dashboard", headers=auth_header(admin)).json()
    assert body["satisfaction"] == {
        "total": 3,
        "average": 3.67,
        "distribution": {"1": 0, "2": 1, "3": 0, "4": 1, "5": 1},
    }
    row = next(r for r in body["by_assignee"] if r["id"] == tecnico.id)
    assert (row["avg_rating"], row["ratings"]) == (3.67, 3)

    mine = client.get("/dashboard", headers=auth_header(tecnico)).json()
    assert mine["satisfaction"]["total"] == 3

def test_dashboard_sem_notas(client: TestClient, admin: User):
    body = client.get("/dashboard", headers=auth_header(admin)).json()
    assert body["satisfaction"] == {"total": 0, "average": None, "distribution": {str(n): 0 for n in range(1, 6)}}
