from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.models import Role, User
from app.schemas.common import Page, error_responses
from app.schemas.ticket import AssigneeUpdate, StatusChange, TicketCreate, TicketFilters, TicketOut, TicketUpdate
from app.services import tickets as ticket_service

router = APIRouter(prefix="/tickets", tags=["chamados"], responses=error_responses(401))


@router.get("", response_model=Page[TicketOut])
def list_tickets(filters: Annotated[TicketFilters, Query()], db: DbSession, user: CurrentUser):
    """Chamados visíveis para o usuário, com os críticos primeiro e depois os mais antigos.

    Os filtros se combinam (status E prioridade E período...). Para escolher vários status ou prioridades,
    repita o parâmetro: `?status=ABERTO&status=EM_ANDAMENTO`.
    """
    items, total = ticket_service.list_tickets(db, user, filters)
    return Page(items=items, total=total, page=filters.page, page_size=filters.page_size)


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED, responses=error_responses(409))
def create_ticket(data: TicketCreate, db: DbSession, user: CurrentUser):
    """Abre um chamado em nome do usuário logado, com status ABERTO e prazo calculado pela prioridade."""
    return ticket_service.create_ticket(db, data, user)


@router.get("/{ticket_id}", response_model=TicketOut, responses=error_responses(404))
def get_ticket(ticket_id: int, db: DbSession, user: CurrentUser):
    return ticket_service.get_ticket(db, ticket_id, user)


@router.patch("/{ticket_id}", response_model=TicketOut, responses=error_responses(403, 404, 409))
def update_ticket(ticket_id: int, data: TicketUpdate, db: DbSession, user: CurrentUser):
    """Edita título, descrição, categoria e prioridade, conforme a permissão do perfil."""
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    return ticket_service.update_ticket(db, ticket, data, user)


@router.put("/{ticket_id}/assignee", response_model=TicketOut, responses=error_responses(403, 404, 409))
def assign_ticket(
    ticket_id: int, data: AssigneeUpdate, db: DbSession, user: User = Depends(require_roles(Role.ADMIN))
):
    """Admin atribui, reatribui ou remove (`null`) o responsável."""
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    return ticket_service.assign_ticket(db, ticket, data.assigned_to_id, user)


@router.post("/{ticket_id}/assume", response_model=TicketOut, responses=error_responses(403, 404, 409))
def assume_ticket(ticket_id: int, db: DbSession, user: User = Depends(require_roles(Role.TECNICO))):
    """O técnico logado vira o responsável por um chamado ABERTO e sem responsável (o admin usa `/assignee`)."""
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    return ticket_service.assume_ticket(db, ticket, user)


@router.post("/{ticket_id}/status", response_model=TicketOut, responses=error_responses(403, 404, 409))
def change_status(ticket_id: int, data: StatusChange, db: DbSession, user: CurrentUser):
    """Muda o status seguindo o fluxo permitido. Transição inválida responde 409.

    - EM_ANDAMENTO → RESOLVIDO exige `solution`
    - RESOLVIDO → EM_ANDAMENTO (recusar a solução) e FECHADO → ABERTO (reabrir) exigem `reason`,
      que é gravado como comentário
    """
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    return ticket_service.change_status(db, ticket, data, user)


@router.delete("/{ticket_id}", response_model=TicketOut, responses=error_responses(403, 404, 409))
def archive_ticket(ticket_id: int, db: DbSession, user: User = Depends(require_roles(Role.ADMIN))):
    """Arquiva o chamado (some das listagens). Não existe exclusão física."""
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    return ticket_service.archive_ticket(db, ticket, user)
