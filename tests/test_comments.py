import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Category, Role, User
from conftest import assume, auth_header, change_status, create_user, open_ticket


def comment(client: TestClient, user: User, ticket_id: int, message: str = "Alguma novidade?"):
    return client.post(f"/tickets/{ticket_id}/comments", headers=auth_header(user), json={"message": message})


# --- Comentários ---


def test_comentario_fica_ligado_ao_autor(client: TestClient, solicitante: User, tecnico: User, em_andamento: dict):
    tid = em_andamento["id"]

    response = comment(client, solicitante, tid, "  A impressora fez um barulho estranho.  ")
    comment(client, tecnico, tid, "Vou verificar agora.")

    assert response.status_code == 201
    assert response.json()["user"] == {"id": solicitante.id, "name": solicitante.name}
    assert response.json()["message"] == "A impressora fez um barulho estranho."
    listed = client.get(f"/tickets/{tid}/comments", headers=auth_header(solicitante)).json()
    assert [(c["user"]["id"], c["message"]) for c in listed] == [
        (solicitante.id, "A impressora fez um barulho estranho."),
        (tecnico.id, "Vou verificar agora."),
    ]


def test_corpo_nao_escolhe_o_autor(client: TestClient, solicitante: User, admin: User, em_andamento: dict):
    response = client.post(
        f"/tickets/{em_andamento['id']}/comments",
        headers=auth_header(solicitante),
        json={"message": "Oi", "user_id": admin.id},
    )

    assert response.json()["user"]["id"] == solicitante.id


@pytest.mark.parametrize("message", ["", "   ", "x" * 5001])
def test_mensagem_vazia_ou_gigante_e_recusada(client: TestClient, solicitante: User, em_andamento: dict, message: str):
    assert comment(client, solicitante, em_andamento["id"], message).status_code == 422


def test_comenta_em_chamado_resolvido(client: TestClient, solicitante: User, resolvido: dict):
    assert comment(client, solicitante, resolvido["id"], "Vou testar e aviso.").status_code == 201


def test_nao_comenta_em_chamado_fechado(client: TestClient, admin: User, solicitante: User, fechado: dict):
    response = comment(client, solicitante, fechado["id"])

    assert response.status_code == 409
    assert comment(client, admin, fechado["id"]).status_code == 409


def test_nao_comenta_em_chamado_arquivado(client: TestClient, admin: User, em_andamento: dict):
    client.delete(f"/tickets/{em_andamento['id']}", headers=auth_header(admin))

    assert comment(client, admin, em_andamento["id"]).status_code == 409


def test_so_comenta_e_le_quem_ve_o_chamado(client: TestClient, db: Session, tecnico: User, em_andamento: dict):
    outro_solicitante = create_user(db, Role.SOLICITANTE, "outro@teste.dev")
    outro_tecnico = create_user(db, Role.TECNICO, "outro.tecnico@teste.dev")
    tid = em_andamento["id"]

    for user in (outro_solicitante, outro_tecnico):
        assert comment(client, user, tid).status_code == 404
        assert client.get(f"/tickets/{tid}/comments", headers=auth_header(user)).status_code == 404
        assert client.get(f"/tickets/{tid}/history", headers=auth_header(user)).status_code == 404


def test_tecnico_comenta_em_chamado_disponivel(
    client: TestClient, tecnico: User, solicitante: User, category: Category
):
    ticket = open_ticket(client, solicitante, category)

    assert comment(client, tecnico, ticket["id"], "Posso assumir à tarde.").status_code == 201


def test_comentarios_nao_podem_ser_editados_nem_apagados(client: TestClient, admin: User, em_andamento: dict):
    created = comment(client, admin, em_andamento["id"]).json()
    url = f"/tickets/{em_andamento['id']}/comments/{created['id']}"

    assert client.patch(url, headers=auth_header(admin), json={"message": "editado"}).status_code in (404, 405)
    assert client.delete(url, headers=auth_header(admin)).status_code in (404, 405)


def test_motivo_da_reabertura_aparece_nos_comentarios(client: TestClient, solicitante: User, fechado: dict):
    change_status(client, solicitante, fechado["id"], "ABERTO", reason="O problema voltou.")

    listed = client.get(f"/tickets/{fechado['id']}/comments", headers=auth_header(solicitante)).json()

    assert listed[-1]["message"] == "O problema voltou."


def test_comentarios_exigem_login(client: TestClient, em_andamento: dict):
    assert client.get(f"/tickets/{em_andamento['id']}/comments").status_code == 401


# --- Histórico ---


def test_historico_reconstroi_a_vida_do_chamado(
    client: TestClient, admin: User, solicitante: User, tecnico: User, category: Category
):
    tid = open_ticket(client, solicitante, category)["id"]
    assume(client, tecnico, tid)
    client.patch(f"/tickets/{tid}", headers=auth_header(tecnico), json={"priority": "ALTA"})
    change_status(client, tecnico, tid, "EM_ANDAMENTO")
    change_status(client, tecnico, tid, "RESOLVIDO", solution="Toner trocado.")
    change_status(client, solicitante, tid, "FECHADO")

    response = client.get(f"/tickets/{tid}/history", headers=auth_header(solicitante))

    assert response.status_code == 200
    events = [(e["action"], e["user"]["id"], e["old_value"], e["new_value"]) for e in response.json()]
    assert events == [
        ("CRIADO", solicitante.id, None, "ABERTO"),
        ("ATRIBUIDO", tecnico.id, None, tecnico.name),
        ("PRIORIDADE_ALTERADA", tecnico.id, "MEDIA", "ALTA"),
        ("STATUS_ALTERADO", tecnico.id, "ABERTO", "EM_ANDAMENTO"),
        ("SOLUCAO_REGISTRADA", tecnico.id, None, "Toner trocado."),
        ("STATUS_ALTERADO", tecnico.id, "EM_ANDAMENTO", "RESOLVIDO"),
        ("STATUS_ALTERADO", solicitante.id, "RESOLVIDO", "FECHADO"),
    ]


def test_comentar_nao_gera_historico(client: TestClient, admin: User, em_andamento: dict):
    url = f"/tickets/{em_andamento['id']}/history"
    before = len(client.get(url, headers=auth_header(admin)).json())

    comment(client, admin, em_andamento["id"])

    assert len(client.get(url, headers=auth_header(admin)).json()) == before


def test_admin_ve_historico_de_chamado_arquivado(client: TestClient, admin: User, em_andamento: dict):
    client.delete(f"/tickets/{em_andamento['id']}", headers=auth_header(admin))

    history = client.get(f"/tickets/{em_andamento['id']}/history", headers=auth_header(admin)).json()

    assert history[-1]["action"] == "ARQUIVADO"
