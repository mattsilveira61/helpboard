from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.comment import CommentCreate, CommentOut, HistoryOut
from app.services import comments as comment_service
from app.services import tickets as ticket_service

router = APIRouter(prefix="/tickets/{ticket_id}", tags=["comentários e histórico"])


@router.get("/comments", response_model=list[CommentOut])
def list_comments(ticket_id: int, db: DbSession, user: CurrentUser):
    """Comentários do chamado, do mais antigo para o mais novo."""
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    return comment_service.list_comments(db, ticket)


@router.post("/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED)
def add_comment(ticket_id: int, data: CommentCreate, db: DbSession, user: CurrentUser):
    """Comenta no chamado em nome do usuário logado. Chamado fechado ou arquivado responde 409."""
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    return comment_service.add_comment(db, ticket, data.message, user)


@router.get("/history", response_model=list[HistoryOut])
def list_history(ticket_id: int, db: DbSession, user: CurrentUser):
    """Linha do tempo de tudo o que mudou no chamado: quem fez, o quê, valor antigo e novo."""
    ticket = ticket_service.get_ticket(db, ticket_id, user)
    return comment_service.list_history(db, ticket)
