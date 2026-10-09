from datetime import datetime, timezone

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Category, Comment, Priority, Role, Ticket, TicketStatus, User
from app.services.sla import calculate_sla_deadline


def make_user(db: Session, email: str = "teste@helpboard.dev", role: Role = Role.SOLICITANTE) -> User:
    user = User(name="Teste", email=email, password_hash="x", role=role)
    db.add(user)
    db.flush()
    return user


def make_ticket(db: Session, **overrides) -> Ticket:
    requester = overrides.pop("requester", None) or make_user(db)
    category = overrides.pop("category", None) or Category(name="Categoria de teste")
    now = datetime.now(timezone.utc)
    fields = dict(
        title="Computador não liga",
        description="Aperto o botão e nada acontece.",
        priority=Priority.MEDIA,
        sla_deadline=calculate_sla_deadline(now, Priority.MEDIA),
    )
    ticket = Ticket(requester=requester, category=category, **(fields | overrides))
    db.add(ticket)
    db.flush()
    return ticket


def test_migration_cria_todas_as_tabelas(db: Session):
    tables = set(inspect(db.connection()).get_table_names())
    assert {"users", "categories", "tickets", "comments", "ticket_history"} <= tables


def test_chamado_novo_comeca_aberto_e_sem_responsavel(db: Session):
    ticket = make_ticket(db)
    db.refresh(ticket)

    assert ticket.status == TicketStatus.ABERTO
    assert ticket.assigned_to_id is None
    assert ticket.is_archived is False
    assert ticket.created_at is not None


def test_email_e_unico(db: Session):
    make_user(db, email="repetido@helpboard.dev")
    with pytest.raises(IntegrityError, match="uq_users_email"):
        make_user(db, email="repetido@helpboard.dev")


def test_nome_de_categoria_e_unico(db: Session):
    db.add(Category(name="Rede"))
    db.flush()
    db.add(Category(name="Rede"))
    with pytest.raises(IntegrityError, match="uq_categories_name"):
        db.flush()


@pytest.mark.parametrize("status", [TicketStatus.RESOLVIDO, TicketStatus.FECHADO])
def test_resolvido_ou_fechado_exige_solucao(db: Session, status: TicketStatus):
    tecnico = make_user(db, email="tec@helpboard.dev", role=Role.TECNICO)
    now = datetime.now(timezone.utc)
    with pytest.raises(IntegrityError, match="ck_tickets_solution_required"):
        make_ticket(db, status=status, assigned_to=tecnico, resolved_at=now, closed_at=now)


def test_em_andamento_exige_responsavel(db: Session):
    with pytest.raises(IntegrityError, match="ck_tickets_in_progress_has_assignee"):
        make_ticket(db, status=TicketStatus.EM_ANDAMENTO)


def test_fechado_exige_data_de_fechamento(db: Session):
    tecnico = make_user(db, email="tec@helpboard.dev", role=Role.TECNICO)
    with pytest.raises(IntegrityError, match="ck_tickets_closed_at_required"):
        make_ticket(
            db,
            status=TicketStatus.FECHADO,
            assigned_to=tecnico,
            solution="Resolvido.",
            resolved_at=datetime.now(timezone.utc),
        )


def test_titulo_curto_demais_e_recusado(db: Session):
    with pytest.raises(IntegrityError, match="ck_tickets_title_length"):
        make_ticket(db, title="  ab  ")


def test_comentario_vazio_e_recusado(db: Session):
    ticket = make_ticket(db)
    db.add(Comment(ticket=ticket, user=ticket.requester, message="   "))
    with pytest.raises(IntegrityError, match="ck_comments_message_not_empty"):
        db.flush()


def test_banco_recusa_status_invalido_mesmo_via_sql(db: Session):
    ticket = make_ticket(db)
    with pytest.raises(IntegrityError, match="ck_tickets_ticket_status"):
        db.execute(text("UPDATE tickets SET status = 'CANCELADO' WHERE id = :id"), {"id": ticket.id})


def test_nao_apaga_usuario_com_chamados(db: Session):
    ticket = make_ticket(db)
    with pytest.raises(IntegrityError, match="fk_tickets_requester_id_users"):
        db.execute(text("DELETE FROM users WHERE id = :id"), {"id": ticket.requester_id})
