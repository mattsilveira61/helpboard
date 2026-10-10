from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, Comment, Role, Ticket, TicketHistory, User
from conftest import assume, auth_header, change_status, create_user, history_actions, open_ticket


# --- Criação (Regras 1, 2, 3 e 11) ---


def test_solicitante_abre_chamado(client: TestClient, db: Session, solicitante: User, category: Category):
    ticket = open_ticket(client, solicitante, category, priority="ALTA")

    assert ticket["status"] == "ABERTO"
    assert ticket["requester"] == {"id": solicitante.id, "name": solicitante.name}
    assert ticket["assigned_to"] is None
    assert ticket["category"]["name"] == "Hardware"
    assert ticket["is_overdue"] is False
    created = datetime.fromisoformat(ticket["created_at"])
    assert datetime.fromisoformat(ticket["sla_deadline"]) - created == timedelta(hours=8)
    assert history_actions(db, ticket["id"]) == ["CRIADO"]


def test_corpo_nao_escolhe_solicitante_nem_status(
    client: TestClient, solicitante: User, admin: User, tecnico: User, category: Category
):
    ticket = open_ticket(
        client, solicitante, category, requester_id=admin.id, status="FECHADO", assigned_to_id=tecnico.id
    )

    assert ticket["requester"]["id"] == solicitante.id
    assert ticket["status"] == "ABERTO"
    assert ticket["assigned_to"] is None


def test_nao_abre_chamado_em_categoria_inativa_ou_inexistente(
    client: TestClient, db: Session, solicitante: User, category: Category
):
    category.is_active = False
    db.flush()
    payload = {"title": "Teste", "description": "x", "priority": "BAIXA"}

    for category_id in (category.id, 999_999):
        response = client.post("/tickets", headers=auth_header(solicitante), json=payload | {"category_id": category_id})
        assert response.status_code == 409


@pytest.mark.parametrize("title", ["ab", "   ab   ", "x" * 121])
def test_titulo_precisa_ter_de_3_a_120_caracteres(
    client: TestClient, solicitante: User, category: Category, title: str
):
    payload = {"title": title, "description": "x", "category_id": category.id, "priority": "BAIXA"}

    assert client.post("/tickets", headers=auth_header(solicitante), json=payload).status_code == 422


@pytest.mark.parametrize("missing", [{"description": None}, {"description": "   "}, {"priority": None}])
def test_descricao_e_prioridade_sao_obrigatorias(
    client: TestClient, solicitante: User, category: Category, missing: dict
):
    payload = {"title": "Teste", "description": "x", "category_id": category.id, "priority": "BAIXA"} | missing
    payload = {key: value for key, value in payload.items() if value is not None}

    assert client.post("/tickets", headers=auth_header(solicitante), json=payload).status_code == 422


def test_chamado_com_prazo_vencido_aparece_atrasado(
    client: TestClient, db: Session, solicitante: User, category: Category
):
    ticket = open_ticket(client, solicitante, category)
    db.get(Ticket, ticket["id"]).sla_deadline = datetime.now().astimezone() - timedelta(hours=1)
    db.flush()

    assert client.get(f"/tickets/{ticket['id']}", headers=auth_header(solicitante)).json()["is_overdue"] is True


def test_chamados_exigem_login(client: TestClient):
    assert client.get("/tickets").status_code == 401
    assert client.post("/tickets", json={}).status_code == 401


# --- Visibilidade (seção 3) ---


def ids(response) -> set[int]:
    return {t["id"] for t in response.json()["items"]}


def test_solicitante_ve_so_os_proprios(client: TestClient, db: Session, solicitante: User, category: Category):
    outro = create_user(db, Role.SOLICITANTE, "outro@teste.dev")
    meu = open_ticket(client, solicitante, category)
    dele = open_ticket(client, outro, category)

    assert ids(client.get("/tickets", headers=auth_header(solicitante))) == {meu["id"]}
    assert client.get(f"/tickets/{meu['id']}", headers=auth_header(solicitante)).status_code == 200
    assert client.get(f"/tickets/{dele['id']}", headers=auth_header(solicitante)).status_code == 404


def test_tecnico_ve_os_seus_e_os_disponiveis(
    client: TestClient, db: Session, solicitante: User, tecnico: User, admin: User, category: Category
):
    outro_tecnico = create_user(db, Role.TECNICO, "outro.tecnico@teste.dev")
    disponivel = open_ticket(client, solicitante, category)
    meu = open_ticket(client, solicitante, category)
    do_outro = open_ticket(client, solicitante, category)
    assume(client, tecnico, meu["id"])
    assume(client, outro_tecnico, do_outro["id"])

    assert ids(client.get("/tickets", headers=auth_header(tecnico))) == {disponivel["id"], meu["id"]}
    assert client.get(f"/tickets/{do_outro['id']}", headers=auth_header(tecnico)).status_code == 404
    assert client.get("/tickets", headers=auth_header(admin)).json()["total"] == 3


def test_arquivados_ficam_ocultos_e_so_admin_ve_com_filtro(
    client: TestClient, admin: User, solicitante: User, category: Category
):
    ticket = open_ticket(client, solicitante, category)
    client.delete(f"/tickets/{ticket['id']}", headers=auth_header(admin))

    assert ids(client.get("/tickets", headers=auth_header(admin))) == set()
    assert ids(client.get("/tickets?include_archived=true", headers=auth_header(admin))) == {ticket["id"]}
    assert ids(client.get("/tickets?include_archived=true", headers=auth_header(solicitante))) == set()


def test_lista_criticos_primeiro_e_depois_os_mais_antigos(
    client: TestClient, solicitante: User, category: Category
):
    baixa = open_ticket(client, solicitante, category, priority="BAIXA")
    critica_1 = open_ticket(client, solicitante, category, priority="CRITICA")
    alta = open_ticket(client, solicitante, category, priority="ALTA")
    critica_2 = open_ticket(client, solicitante, category, priority="CRITICA")

    response = client.get("/tickets", headers=auth_header(solicitante))

    assert [t["id"] for t in response.json()["items"]] == [critica_1["id"], critica_2["id"], alta["id"], baixa["id"]]


# --- Edição (matriz da seção 5) ---


def test_solicitante_edita_o_proprio_chamado_aberto(
    client: TestClient, db: Session, solicitante: User, category: Category
):
    ticket = open_ticket(client, solicitante, category)

    response = client.patch(
        f"/tickets/{ticket['id']}", headers=auth_header(solicitante), json={"title": "Impressora do RH quebrada"}
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Impressora do RH quebrada"
    history = db.scalars(select(TicketHistory).where(TicketHistory.ticket_id == ticket["id"])).all()
    assert history[-1].action == "EDITADO"
    assert (history[-1].old_value, history[-1].new_value) == ("Impressora quebrada", "Impressora do RH quebrada")


def test_solicitante_nao_edita_depois_que_o_atendimento_comeca(
    client: TestClient, solicitante: User, em_andamento: dict
):
    response = client.patch(f"/tickets/{em_andamento['id']}", headers=auth_header(solicitante), json={"title": "Novo"})

    assert response.status_code == 403


def test_solicitante_nao_altera_prioridade(client: TestClient, solicitante: User, category: Category):
    ticket = open_ticket(client, solicitante, category)

    response = client.patch(f"/tickets/{ticket['id']}", headers=auth_header(solicitante), json={"priority": "CRITICA"})

    assert response.status_code == 403


def test_responsavel_altera_prioridade_e_o_prazo_e_recalculado(
    client: TestClient, db: Session, tecnico: User, em_andamento: dict
):
    response = client.patch(f"/tickets/{em_andamento['id']}", headers=auth_header(tecnico), json={"priority": "CRITICA"})

    assert response.status_code == 200
    body = response.json()
    created = datetime.fromisoformat(body["created_at"])
    assert datetime.fromisoformat(body["sla_deadline"]) - created == timedelta(hours=4)
    assert history_actions(db, body["id"])[-1] == "PRIORIDADE_ALTERADA"


def test_tecnico_que_nao_e_responsavel_nao_edita(
    client: TestClient, tecnico: User, solicitante: User, category: Category
):
    ticket = open_ticket(client, solicitante, category)  # disponível: o técnico vê, mas não é o responsável

    response = client.patch(f"/tickets/{ticket['id']}", headers=auth_header(tecnico), json={"priority": "ALTA"})

    assert response.status_code == 403


def test_responsavel_nao_edita_titulo(client: TestClient, tecnico: User, em_andamento: dict):
    response = client.patch(f"/tickets/{em_andamento['id']}", headers=auth_header(tecnico), json={"title": "Outro"})

    assert response.status_code == 403


def test_admin_altera_categoria_mas_so_para_uma_ativa(
    client: TestClient, db: Session, admin: User, solicitante: User, category: Category
):
    ticket = open_ticket(client, solicitante, category)
    rede = Category(name="Rede")
    inativa = Category(name="Antiga", is_active=False)
    db.add_all([rede, inativa])
    db.flush()
    url = f"/tickets/{ticket['id']}"

    assert client.patch(url, headers=auth_header(admin), json={"category_id": inativa.id}).status_code == 409
    response = client.patch(url, headers=auth_header(admin), json={"category_id": rede.id})

    assert response.status_code == 200
    assert response.json()["category"]["name"] == "Rede"
    assert history_actions(db, ticket["id"])[-1] == "CATEGORIA_ALTERADA"


def test_chamado_fechado_nao_pode_ser_editado(client: TestClient, admin: User, fechado: dict):
    response = client.patch(f"/tickets/{fechado['id']}", headers=auth_header(admin), json={"priority": "BAIXA"})

    assert response.status_code == 409


# --- Responsável (Regra 4) ---


def test_tecnico_assume_chamado_disponivel(
    client: TestClient, db: Session, tecnico: User, solicitante: User, category: Category
):
    ticket = open_ticket(client, solicitante, category)

    response = assume(client, tecnico, ticket["id"])

    assert response.status_code == 200
    assert response.json()["assigned_to"]["id"] == tecnico.id
    assert response.json()["status"] == "ABERTO"
    assert history_actions(db, ticket["id"]) == ["CRIADO", "ATRIBUIDO"]


def test_tecnico_so_assume_chamado_aberto_e_sem_responsavel(
    client: TestClient, tecnico: User, em_andamento: dict, solicitante: User, category: Category
):
    ja_meu = open_ticket(client, solicitante, category)
    assume(client, tecnico, ja_meu["id"])

    assert assume(client, tecnico, ja_meu["id"]).status_code == 409
    assert assume(client, tecnico, em_andamento["id"]).status_code == 409


@pytest.mark.parametrize("profile", ["solicitante", "admin"])
def test_so_tecnico_usa_assumir(client: TestClient, request, solicitante: User, category: Category, profile: str):
    ticket = open_ticket(client, solicitante, category)

    assert assume(client, request.getfixturevalue(profile), ticket["id"]).status_code == 403


def test_admin_atribui_e_reatribui(
    client: TestClient, db: Session, admin: User, tecnico: User, em_andamento: dict
):
    outro = create_user(db, Role.TECNICO, "outro.tecnico@teste.dev")

    response = client.put(
        f"/tickets/{em_andamento['id']}/assignee", headers=auth_header(admin), json={"assigned_to_id": outro.id}
    )

    assert response.status_code == 200
    assert response.json()["assigned_to"]["id"] == outro.id
    last = db.scalars(select(TicketHistory).where(TicketHistory.ticket_id == em_andamento["id"])).all()[-1]
    assert (last.action, last.old_value, last.new_value) == ("ATRIBUIDO", tecnico.name, outro.name)


def test_responsavel_precisa_ser_tecnico_ou_admin_ativo(
    client: TestClient, db: Session, admin: User, solicitante: User, category: Category
):
    ticket = open_ticket(client, solicitante, category)
    inativo = create_user(db, Role.TECNICO, "inativo@teste.dev", is_active=False)
    url = f"/tickets/{ticket['id']}/assignee"

    for user_id in (solicitante.id, inativo.id, 999_999):
        assert client.put(url, headers=auth_header(admin), json={"assigned_to_id": user_id}).status_code == 409
    assert client.put(url, headers=auth_header(admin), json={"assigned_to_id": admin.id}).status_code == 200


def test_chamado_em_andamento_nao_fica_sem_responsavel(client: TestClient, admin: User, em_andamento: dict):
    response = client.put(
        f"/tickets/{em_andamento['id']}/assignee", headers=auth_header(admin), json={"assigned_to_id": None}
    )

    assert response.status_code == 409


def test_tecnico_nao_atribui(client: TestClient, tecnico: User, solicitante: User, category: Category):
    ticket = open_ticket(client, solicitante, category)

    response = client.put(
        f"/tickets/{ticket['id']}/assignee", headers=auth_header(tecnico), json={"assigned_to_id": tecnico.id}
    )

    assert response.status_code == 403


def test_chamado_fechado_nao_troca_de_responsavel(client: TestClient, admin: User, fechado: dict):
    response = client.put(
        f"/tickets/{fechado['id']}/assignee", headers=auth_header(admin), json={"assigned_to_id": admin.id}
    )

    assert response.status_code == 409


# --- Status (seção 4, Regras 5 e 6) ---


def test_fluxo_completo_de_um_chamado(
    client: TestClient, db: Session, solicitante: User, tecnico: User, category: Category
):
    ticket = open_ticket(client, solicitante, category)
    tid = ticket["id"]

    assert assume(client, tecnico, tid).status_code == 200
    assert change_status(client, tecnico, tid, "EM_ANDAMENTO").json()["status"] == "EM_ANDAMENTO"

    resolvido = change_status(client, tecnico, tid, "RESOLVIDO", solution="Toner trocado.").json()
    assert resolvido["status"] == "RESOLVIDO"
    assert resolvido["solution"] == "Toner trocado."
    assert resolvido["resolved_at"] is not None

    fechado = change_status(client, solicitante, tid, "FECHADO").json()
    assert fechado["status"] == "FECHADO"
    assert fechado["closed_at"] is not None

    reaberto = change_status(client, solicitante, tid, "ABERTO", reason="Voltou a falhar.").json()
    assert reaberto["status"] == "ABERTO"
    assert reaberto["solution"] is reaberto["resolved_at"] is reaberto["closed_at"] is None
    assert reaberto["assigned_to"]["id"] == tecnico.id

    assert history_actions(db, tid) == [
        "CRIADO", "ATRIBUIDO", "STATUS_ALTERADO", "SOLUCAO_REGISTRADA", "STATUS_ALTERADO", "STATUS_ALTERADO",
        "REABERTO",
    ]
    # A solução antiga continua guardada no histórico, e o motivo vira comentário
    solucao = db.scalar(select(TicketHistory).where(TicketHistory.ticket_id == tid, TicketHistory.action == "SOLUCAO_REGISTRADA"))
    assert solucao.new_value == "Toner trocado."
    comment = db.scalar(select(Comment).where(Comment.ticket_id == tid))
    assert (comment.user_id, comment.message) == (solicitante.id, "Voltou a falhar.")


def test_nao_inicia_atendimento_sem_responsavel(
    client: TestClient, admin: User, solicitante: User, category: Category
):
    ticket = open_ticket(client, solicitante, category)

    assert change_status(client, admin, ticket["id"], "EM_ANDAMENTO").status_code == 409


def test_resolver_exige_solucao(client: TestClient, tecnico: User, em_andamento: dict):
    response = change_status(client, tecnico, em_andamento["id"], "RESOLVIDO")

    assert response.status_code == 409
    assert "solução" in response.json()["detail"]


@pytest.mark.parametrize(
    ("fixture", "status"),
    [("em_andamento", "FECHADO"), ("resolvido", "ABERTO"), ("fechado", "EM_ANDAMENTO"), ("fechado", "RESOLVIDO")],
)
def test_transicoes_fora_do_fluxo_sao_recusadas(client: TestClient, request, admin: User, fixture: str, status: str):
    ticket = request.getfixturevalue(fixture)

    response = change_status(client, admin, ticket["id"], status, solution="x", reason="x")

    assert response.status_code == 409


def test_aberto_nao_pula_para_resolvido(client: TestClient, admin: User, solicitante: User, category: Category):
    ticket = open_ticket(client, solicitante, category)

    assert change_status(client, admin, ticket["id"], "RESOLVIDO", solution="x").status_code == 409


def test_reabrir_exige_motivo(client: TestClient, solicitante: User, fechado: dict):
    assert change_status(client, solicitante, fechado["id"], "ABERTO").status_code == 409


def test_solicitante_recusa_a_solucao_com_motivo(
    client: TestClient, db: Session, solicitante: User, resolvido: dict
):
    assert change_status(client, solicitante, resolvido["id"], "EM_ANDAMENTO").status_code == 409

    response = change_status(client, solicitante, resolvido["id"], "EM_ANDAMENTO", reason="Continua sem imprimir.")

    assert response.status_code == 200
    assert response.json()["status"] == "EM_ANDAMENTO"
    assert response.json()["resolved_at"] is None
    assert db.scalar(select(Comment.message).where(Comment.ticket_id == resolvido["id"])) == "Continua sem imprimir."


def test_responsavel_devolve_a_fila(client: TestClient, tecnico: User, em_andamento: dict):
    response = change_status(client, tecnico, em_andamento["id"], "ABERTO")

    assert response.status_code == 200
    assert response.json()["status"] == "ABERTO"
    assert response.json()["assigned_to"] is None


def test_solicitante_nao_resolve(client: TestClient, solicitante: User, em_andamento: dict):
    response = change_status(client, solicitante, em_andamento["id"], "RESOLVIDO", solution="Resolvi sozinho.")

    assert response.status_code == 403


def test_tecnico_nao_fecha_nem_reabre(client: TestClient, tecnico: User, resolvido: dict):
    assert change_status(client, tecnico, resolvido["id"], "FECHADO").status_code == 403


def test_admin_faz_qualquer_transicao_permitida(client: TestClient, admin: User, resolvido: dict):
    assert change_status(client, admin, resolvido["id"], "FECHADO").status_code == 200
    assert change_status(client, admin, resolvido["id"], "ABERTO", reason="Pedido da diretoria.").status_code == 200


def test_falha_no_historico_desfaz_a_mudanca(
    client: TestClient, db: Session, tecnico: User, em_andamento: dict, monkeypatch: pytest.MonkeyPatch
):
    """Regra 8: a mudança e o histórico vão juntos no mesmo commit; se um falha, nenhum fica gravado."""
    def broken_log(*args, **kwargs):
        raise RuntimeError("histórico fora do ar")

    before = history_actions(db, em_andamento["id"])
    monkeypatch.setattr("app.services.tickets._log", broken_log)

    response = change_status(client, tecnico, em_andamento["id"], "RESOLVIDO", solution="Toner trocado.")

    assert response.status_code == 500
    db.rollback()  # o que a sessão da requisição faz ao ser fechada sem commit
    ticket = db.get(Ticket, em_andamento["id"])
    assert ticket.status == "EM_ANDAMENTO"
    assert ticket.solution is None
    assert history_actions(db, ticket.id) == before


# --- Arquivamento (Regra 9) ---


def test_admin_arquiva_em_vez_de_excluir(
    client: TestClient, db: Session, admin: User, solicitante: User, category: Category
):
    ticket = open_ticket(client, solicitante, category)

    response = client.delete(f"/tickets/{ticket['id']}", headers=auth_header(admin))

    assert response.status_code == 200
    assert response.json()["is_archived"] is True
    assert db.get(Ticket, ticket["id"]) is not None  # continua no banco
    assert history_actions(db, ticket["id"])[-1] == "ARQUIVADO"
    assert client.delete(f"/tickets/{ticket['id']}", headers=auth_header(admin)).status_code == 409


@pytest.mark.parametrize("profile", ["tecnico", "solicitante"])
def test_so_admin_arquiva(client: TestClient, request, solicitante: User, category: Category, profile: str):
    ticket = open_ticket(client, solicitante, category)

    response = client.delete(f"/tickets/{ticket['id']}", headers=auth_header(request.getfixturevalue(profile)))

    assert response.status_code == 403


def test_chamado_arquivado_nao_muda_mais(client: TestClient, admin: User, em_andamento: dict):
    client.delete(f"/tickets/{em_andamento['id']}", headers=auth_header(admin))

    assert change_status(client, admin, em_andamento["id"], "ABERTO").status_code == 409
    assert client.patch(f"/tickets/{em_andamento['id']}", headers=auth_header(admin), json={"title": "Novo"}).status_code == 409
