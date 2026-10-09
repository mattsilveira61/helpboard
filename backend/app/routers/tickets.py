from fastapi import APIRouter, Depends, status

from app.core.deps import CurrentUser, DbSession, require_roles
from app.models import Role, User
from app.schemas.ticket import AssigneeUpdate, StatusChange, TicketCreate, TicketOut, TicketUpdate
from app.services import tickets as ticket_service

router = APIRouter(prefix="/tickets", tags=["chamados"])


@router.get("", response_model=list[TicketOut])
def list_tickets(db: DbSession, user: CurrentUser, include_archived: bool = False):
    """Chamados visíveis para o usuário, com os críticos primeiro e depois os mais antigos.

    `include_archived` só tem efeito para o admin.
    """
    return ticket_service.list_tickets(db, user, include_archived=include_archived)


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(data: TicketCreate, db: DbSession, user: CurrentUser):
    """Abre um chamado em nome do usuário logado, com status ABERTO e prazo calculado pela prioridade."""
    return ticket_service.create_ticket(db, data, user)


@router.get("/{ticket_id}", response_model=TicketOut)
def get_ticket(ticket_id: int, db: DbSession, user: CurrentUser):
    return ticket_service.get_ticket(db, ticket_id, user)


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id: int, data: TicketUpdate, db: DbSession, user: CurrentUser):
    """Edita título, descrição, categoria e prioridade, conforme a permissão do perfil."""
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    return ticket_service.update_ticket(db, ticket, data, user)


@router.put("/{ticket_id}/assignee", response_model=TicketOut)
def assign_ticket(
    ticket_id: int, data: AssigneeUpdate, db: DbSession, user: User = Depends(require_roles(Role.ADMIN))
):
    """Admin atribui, reatribui ou remove (`null`) o responsável."""
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    return ticket_service.assign_ticket(db, ticket, data.assigned_to_id, user)


@router.post("/{ticket_id}/assume", response_model=TicketOut)
def assume_ticket(ticket_id: int, db: DbSession, user: User = Depends(require_roles(Role.TECNICO))):
    """O técnico logado vira o responsável por um chamado ABERTO e sem responsável (o admin usa `/assignee`)."""
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    return ticket_service.assume_ticket(db, ticket, user)


@router.post("/{ticket_id}/status", response_model=TicketOut)
def change_status(ticket_id: int, data: StatusChange, db: DbSession, user: CurrentUser):
    """Muda o status seguindo o fluxo permitido. Transição inválida responde 409.

    - EM_ANDAMENTO → RESOLVIDO exige `solution`
    - RESOLVIDO → EM_ANDAMENTO (recusar a solução) e FECHADO → ABERTO (reabrir) exigem `reason`,
      que é gravado como comentário
    """
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    return ticket_service.change_status(db, ticket, data, user)


@router.delete("/{ticket_id}", response_model=TicketOut)
def archive_ticket(ticket_id: int, db: DbSession, user: User = Depends(require_roles(Role.ADMIN))):
    """Arquiva o chamado (some das listagens). Não existe exclusão física."""
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    return ticket_service.archive_ticket(db, ticket, user)
