# Importar todos os models aqui garante que o Base.metadata conheça todas as tabelas
# (o Alembic depende disso para gerar as migrations).
from app.models.category import Category
from app.models.comment import Comment
from app.models.enums import HistoryAction, Priority, Role, TicketStatus
from app.models.ticket import Ticket
from app.models.ticket_history import TicketHistory
from app.models.user import User

__all__ = [
    "Category",
    "Comment",
    "HistoryAction",
    "Priority",
    "Role",
    "Ticket",
    "TicketHistory",
    "TicketStatus",
    "User",
]
