"""Indicadores de gestão. Cada um é calculado pelo banco (GROUP BY, COUNT ... FILTER, JOIN), sem carregar chamados.

Escopo: o admin vê todos os chamados; o técnico vê só os seus números (os atribuídos a ele).
Arquivados nunca entram na conta.
"""

from datetime import date, timedelta

from sqlalchemy import ColumnElement, Date, and_, bindparam, cast, func, or_, select
from sqlalchemy.orm import Session

from app.core import clock
from app.models import Category, Priority, Role, Ticket, TicketStatus, User
from app.schemas.dashboard import (
    AssigneeStats,
    Backlog,
    CategoryCount,
    CreatedStats,
    DashboardOut,
    DashboardParams,
    DayCount,
    Period,
    ResolvedStats,
)

UNRESOLVED = (TicketStatus.ABERTO, TicketStatus.EM_ANDAMENTO)

# Horas entre a abertura e a solução
RESOLUTION_HOURS = func.extract("epoch", Ticket.resolved_at - Ticket.created_at) / 3600


def _scope(user: User) -> list[ColumnElement[bool]]:
    conditions = [Ticket.is_archived.is_(False)]
    if user.role == Role.TECNICO:
        conditions.append(Ticket.assigned_to_id == user.id)
    return conditions


def _between(column, start: date, end: date) -> ColumnElement[bool]:
    """Dias inclusivos no calendário da empresa."""
    return and_(column >= clock.start_of_day(start), column < clock.start_of_day(end + timedelta(days=1)))


def _local_day(column) -> ColumnElement[date]:
    """Converte o timestamp (UTC) para o dia no fuso da empresa.

    O fuso vai escrito na própria SQL (literal_execute): como parâmetro, o Postgres não reconheceria
    a expressão do SELECT e a do GROUP BY como iguais.
    """
    tz = bindparam("tz", clock.company_tz().key, literal_execute=True)
    return cast(func.timezone(tz, column), Date)


def _hours(value) -> float | None:
    return None if value is None else round(float(value), 1)


def _backlog(db: Session, scope: list[ColumnElement[bool]]) -> Backlog:
    open_, in_progress, critical, overdue = db.execute(
        select(
            func.count().filter(Ticket.status == TicketStatus.ABERTO),
            func.count().filter(Ticket.status == TicketStatus.EM_ANDAMENTO),
            func.count().filter(Ticket.priority == Priority.CRITICA),
            func.count().filter(Ticket.sla_deadline < clock.now()),
        ).where(*scope, Ticket.status.in_(UNRESOLVED))
    ).one()
    # A fila de disponíveis é a mesma para todos: é dela que os técnicos assumem chamados
    unassigned = db.scalar(
        select(func.count()).where(
            Ticket.is_archived.is_(False), Ticket.status == TicketStatus.ABERTO, Ticket.assigned_to_id.is_(None)
        )
    )
    return Backlog(open=open_, in_progress=in_progress, critical=critical, overdue=overdue, unassigned=unassigned)


def _created(db: Session, scope: list[ColumnElement[bool]], in_period: ColumnElement[bool]) -> CreatedStats:
    rows = db.execute(
        select(Ticket.status, Ticket.priority, func.count())
        .where(*scope, in_period)
        .group_by(Ticket.status, Ticket.priority)
    ).all()
    by_status = dict.fromkeys(TicketStatus, 0)
    by_priority = dict.fromkeys(Priority, 0)
    for status, priority, total in rows:
        by_status[status] += total
        by_priority[priority] += total

    # LEFT JOIN com os filtros no ON: categorias sem chamados no período aparecem com zero
    total = func.count(Ticket.id)
    categories = db.execute(
        select(Category.id, Category.name, total)
        .outerjoin(Ticket, and_(Ticket.category_id == Category.id, *scope, in_period))
        .group_by(Category.id)
        .having(or_(Category.is_active, total > 0))
        .order_by(total.desc(), Category.name)
    ).all()

    return CreatedStats(
        total=sum(by_status.values()),
        by_status=by_status,
        by_priority=by_priority,
        by_category=[CategoryCount(id=id_, name=name, total=count) for id_, name, count in categories],
    )


def _resolved(db: Session, scope: list[ColumnElement[bool]], in_period: ColumnElement[bool]) -> ResolvedStats:
    total, avg_hours = db.execute(select(func.count(), func.avg(RESOLUTION_HOURS)).where(*scope, in_period)).one()
    return ResolvedStats(total=total, avg_resolution_hours=_hours(avg_hours))


def _timeline(db: Session, scope: list[ColumnElement[bool]], params: DashboardParams) -> list[DayCount]:
    def per_day(column) -> dict[date, int]:
        day = _local_day(column)
        query = select(day, func.count()).where(*scope, _between(column, params.start, params.end)).group_by(day)
        return {day: total for day, total in db.execute(query)}

    created, resolved = per_day(Ticket.created_at), per_day(Ticket.resolved_at)
    days = (params.start + timedelta(days=n) for n in range((params.end - params.start).days + 1))
    return [DayCount(day=day, created=created.get(day, 0), resolved=resolved.get(day, 0)) for day in days]


def _by_assignee(
    db: Session, user: User, scope: list[ColumnElement[bool]], resolved_in_period: ColumnElement[bool]
) -> list[AssigneeStats]:
    open_ = func.count().filter(Ticket.status == TicketStatus.ABERTO)
    in_progress = func.count().filter(Ticket.status == TicketStatus.EM_ANDAMENTO)
    resolved = func.count().filter(resolved_in_period)
    query = (
        select(User.id, User.name, open_, in_progress, resolved, func.avg(RESOLUTION_HOURS).filter(resolved_in_period))
        .outerjoin(Ticket, and_(Ticket.assigned_to_id == User.id, *scope))
        .group_by(User.id)
        # Técnicos ativos aparecem mesmo zerados; os demais (admin, desativados) só se tiverem números
        .having(or_(and_(User.role == Role.TECNICO, User.is_active), open_ + in_progress + resolved > 0))
        .order_by(User.name)
    )
    if user.role == Role.TECNICO:
        query = query.where(User.id == user.id)
    return [
        AssigneeStats(id=id_, name=name, open=o, in_progress=p, resolved=r, avg_resolution_hours=_hours(avg))
        for id_, name, o, p, r, avg in db.execute(query).all()
    ]


def get_dashboard(db: Session, user: User, params: DashboardParams) -> DashboardOut:
    scope = _scope(user)
    created_in_period = _between(Ticket.created_at, params.start, params.end)
    resolved_in_period = _between(Ticket.resolved_at, params.start, params.end)
    return DashboardOut(
        scope="TODOS" if user.role == Role.ADMIN else "MEUS",
        period=Period(start=params.start, end=params.end),
        backlog=_backlog(db, scope),
        created=_created(db, scope, created_in_period),
        resolved=_resolved(db, scope, resolved_in_period),
        timeline=_timeline(db, scope, params),
        by_assignee=_by_assignee(db, user, scope, resolved_in_period),
    )
