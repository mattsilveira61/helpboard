from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models import HistoryAction, Role, Ticket, TicketHistory, TicketStatus, User
from app.seed import CATEGORIES, DEMO_TICKETS, USERS, run_seed

PASSWORD = "senha-de-teste"


def test_seed_cria_usuarios_categorias_e_chamados(db: Session):
    totals = run_seed(db, PASSWORD)

    assert totals["users"] == len(USERS)
    assert totals["categories"] == len(CATEGORIES)
    assert totals["tickets"] == len(DEMO_TICKETS)
    # Todo chamado tem ao menos o evento CRIADO no histórico
    assert totals["ticket_history"] >= totals["tickets"]


def test_seed_pode_rodar_mais_de_uma_vez_sem_duplicar(db: Session):
    first = run_seed(db, PASSWORD)
    second = run_seed(db, PASSWORD)
    assert first == second


def test_seed_cria_admin_com_senha_em_hash(db: Session):
    run_seed(db, PASSWORD)
    admin = db.scalar(select(User).where(User.role == Role.ADMIN))

    assert admin.email == "admin@helpboard.dev"
    assert admin.password_hash != PASSWORD
    assert verify_password(PASSWORD, admin.password_hash)


def test_seed_tem_chamados_em_todos_os_status(db: Session):
    run_seed(db, PASSWORD)
    statuses = set(db.scalars(select(Ticket.status).distinct()))
    assert statuses == set(TicketStatus)


def test_historico_do_chamado_fechado_segue_o_fluxo(db: Session):
    run_seed(db, PASSWORD)
    ticket = db.scalar(
        select(Ticket).where(Ticket.status == TicketStatus.FECHADO, Ticket.is_archived.is_(False)).limit(1)
    )
    transitions = [
        (h.old_value, h.new_value) for h in ticket.history if h.action == HistoryAction.STATUS_ALTERADO
    ]

    assert transitions == [("ABERTO", "EM_ANDAMENTO"), ("EM_ANDAMENTO", "RESOLVIDO"), ("RESOLVIDO", "FECHADO")]
    assert ticket.resolved_at <= ticket.closed_at


def test_historico_fica_em_ordem_cronologica(db: Session):
    run_seed(db, PASSWORD)
    out_of_order = db.scalar(
        select(func.count())
        .select_from(TicketHistory)
        .join(Ticket)
        .where(TicketHistory.created_at < Ticket.created_at)
    )
    assert out_of_order == 0
