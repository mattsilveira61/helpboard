"""Popula o banco com os dados iniciais e de demonstração.

Uso (dentro de backend/):  python -m app.seed

- Categorias e usuários: criados só se ainda não existirem (pode rodar quantas vezes quiser).
- Chamados de exemplo: criados só se a tabela de chamados estiver vazia.
- A senha dos usuários demo vem de DEMO_PASSWORD no .env (nunca fica no código).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import (
    Category,
    Comment,
    HistoryAction,
    Priority,
    Role,
    Ticket,
    TicketHistory,
    TicketStatus,
    User,
)
from app.services.sla import calculate_sla_deadline

CATEGORIES = [
    ("Hardware", "Computadores, impressoras, monitores e periféricos"),
    ("Software", "Instalação, atualização e erros de programas"),
    ("Rede", "Internet, Wi-Fi, cabos e VPN"),
    ("Acesso", "Senhas, permissões e criação de contas"),
    ("E-mail", "Caixa de entrada, envio, calendário e configuração"),
    ("Sistema interno", "ERP e sistemas próprios da empresa"),
    ("Outros", "Pedidos que não se encaixam nas demais categorias"),
]

# chave interna → (nome, e-mail, perfil)
USERS = {
    "admin": ("Ana Admin", "admin@helpboard.dev", Role.ADMIN),
    "maria": ("Maria Técnica", "maria@helpboard.dev", Role.TECNICO),
    "carlos": ("Carlos Técnico", "carlos@helpboard.dev", Role.TECNICO),
    "joao": ("João Solicitante", "joao@helpboard.dev", Role.SOLICITANTE),
}


@dataclass
class DemoTicket:
    title: str
    description: str
    category: str
    priority: Priority
    status: TicketStatus
    hours_ago: float
    assignee: str | None = None
    solution: str | None = None
    # (momento, autor, mensagem). O momento vai de 0 (abertura) a 10 (agora).
    comments: tuple[tuple[int, str, str], ...] = ()
    reopened: bool = False
    archived: bool = False
    requester: str = "joao"


A, E, R, F = TicketStatus.ABERTO, TicketStatus.EM_ANDAMENTO, TicketStatus.RESOLVIDO, TicketStatus.FECHADO

DEMO_TICKETS = [
    # --- ABERTO ---
    DemoTicket("Impressora do financeiro não imprime", "A impressora mostra 'erro 49' e não imprime nada.",
               "Hardware", Priority.ALTA, A, 3,
               comments=((5, "joao", "Já tentei desligar e ligar de novo, continua igual."),)),
    DemoTicket("Sem internet na sala de reuniões", "Nenhum cabo de rede da sala de reuniões funciona.",
               "Rede", Priority.CRITICA, A, 9,
               comments=((6, "joao", "A reunião com o cliente é às 15h, precisamos disso funcionando."),)),
    DemoTicket("Instalar o Power BI no meu notebook", "Preciso do Power BI Desktop para os relatórios do mês.",
               "Software", Priority.BAIXA, A, 20),
    DemoTicket("Criar acesso ao sistema para o novo estagiário", "O Pedro começa na segunda-feira no comercial.",
               "Acesso", Priority.MEDIA, A, 30),
    DemoTicket("Caixa de e-mail cheia", "Aparece o aviso de que a caixa atingiu o limite e não recebo mais e-mails.",
               "E-mail", Priority.MEDIA, A, 2),
    DemoTicket("VPN cai a cada 10 minutos", "Trabalhando de casa, a VPN desconecta sozinha o tempo todo.",
               "Rede", Priority.ALTA, A, 120, assignee="carlos",
               solution="Cliente da VPN atualizado para a versão mais recente.", reopened=True,
               comments=((3, "carlos", "Estou analisando os logs da VPN."),
                         (9, "joao", "O problema voltou hoje de manhã, a VPN continua caindo."))),
    # --- EM_ANDAMENTO ---
    DemoTicket("Notebook muito lento depois da atualização", "Desde a atualização de ontem tudo demora para abrir.",
               "Hardware", Priority.MEDIA, E, 26, assignee="maria",
               comments=((4, "maria", "Vou passar na sua mesa às 14h para verificar."),
                         (5, "joao", "Combinado, obrigado!"))),
    DemoTicket("Erro ao emitir nota fiscal no ERP", "O ERP mostra 'certificado inválido' ao emitir qualquer nota.",
               "Sistema interno", Priority.CRITICA, E, 3, assignee="carlos",
               comments=((3, "carlos", "Já identifiquei: o certificado digital venceu. Estou renovando."),)),
    DemoTicket("Outlook não sincroniza o calendário", "As reuniões marcadas no celular não aparecem no computador.",
               "E-mail", Priority.BAIXA, E, 50, assignee="maria"),
    DemoTicket("Monitor piscando", "O monitor da direita pisca de vez em quando e fica preto por alguns segundos.",
               "Hardware", Priority.BAIXA, E, 80, assignee="carlos"),
    DemoTicket("Liberar acesso à pasta do RH", "Preciso acessar a pasta compartilhada do RH para a folha de ponto.",
               "Acesso", Priority.ALTA, E, 5, assignee="maria"),
    # --- RESOLVIDO ---
    DemoTicket("Teclado com teclas falhando", "As teclas A e S só funcionam apertando com força.",
               "Hardware", Priority.BAIXA, R, 48, assignee="carlos",
               solution="Teclado substituído por um novo do estoque."),
    DemoTicket("Planilha corrompida no servidor", "A planilha de orçamento não abre mais: 'arquivo corrompido'.",
               "Software", Priority.ALTA, R, 12, assignee="maria",
               solution="Arquivo restaurado a partir do backup da noite anterior.",
               comments=((7, "maria", "Restaurei a versão de ontem às 23h. Confere se está tudo certo?"),)),
    DemoTicket("Wi-Fi lento no segundo andar", "A internet sem fio está muito lenta desde segunda-feira.",
               "Rede", Priority.MEDIA, R, 40, assignee="carlos",
               solution="Roteador reiniciado e canal alterado para evitar interferência."),
    DemoTicket("Senha do sistema bloqueada", "Errei a senha três vezes e o sistema bloqueou meu usuário.",
               "Acesso", Priority.CRITICA, R, 6, assignee="maria",
               solution="Senha redefinida e usuário desbloqueado."),
    # --- FECHADO ---
    DemoTicket("Instalar o Adobe Reader", "Preciso abrir arquivos PDF dos fornecedores.",
               "Software", Priority.BAIXA, F, 200, assignee="maria", solution="Adobe Reader instalado."),
    DemoTicket("Mouse sem fio parou de funcionar", "O mouse não responde, mesmo depois de reconectar o receptor.",
               "Hardware", Priority.BAIXA, F, 150, assignee="carlos", solution="Pilhas do mouse trocadas.",
               comments=((7, "joao", "Funcionou, obrigado!"),)),
    DemoTicket("Configurar e-mail no celular", "Quero receber os e-mails da empresa no meu celular.",
               "E-mail", Priority.MEDIA, F, 100, assignee="maria",
               solution="Conta configurada no aplicativo Outlook do celular."),
    DemoTicket("Relatório de vendas com valores errados", "O relatório mensal soma vendas de meses anteriores.",
               "Sistema interno", Priority.ALTA, F, 170, assignee="carlos",
               solution="Corrigido o filtro de datas do relatório no ERP."),
    DemoTicket("Pedido de cadeira nova", "Minha cadeira está quebrada e precisa ser trocada.",
               "Outros", Priority.BAIXA, F, 300, assignee="carlos", archived=True,
               solution="Pedido encaminhado ao setor de compras."),
]


def _ensure_categories(db: Session) -> dict[str, Category]:
    existing = {c.name: c for c in db.scalars(select(Category))}
    for name, description in CATEGORIES:
        if name not in existing:
            existing[name] = Category(name=name, description=description)
            db.add(existing[name])
    return existing


def _ensure_users(db: Session, demo_password: str) -> dict[str, User]:
    by_email = {u.email: u for u in db.scalars(select(User))}
    users = {}
    for key, (name, email, role) in USERS.items():
        user = by_email.get(email)
        if user is None:
            user = User(name=name, email=email, role=role, password_hash=hash_password(demo_password))
            db.add(user)
        users[key] = user
    return users


def _build_ticket(spec: DemoTicket, users: dict[str, User], categories: dict[str, Category], now: datetime) -> Ticket:
    """Monta o chamado passando pelo fluxo de status real, gerando o histórico de cada passo."""
    created = now - timedelta(hours=spec.hours_ago)
    step = timedelta(hours=spec.hours_ago) / 10
    requester = users[spec.requester]
    assignee = users[spec.assignee] if spec.assignee else None

    ticket = Ticket(
        title=spec.title,
        description=spec.description,
        category=categories[spec.category],
        priority=spec.priority,
        requester=requester,
        status=TicketStatus.ABERTO,
        sla_deadline=calculate_sla_deadline(created, spec.priority),
        created_at=created,
    )
    last = created

    def log(moment: int, user: User, action: HistoryAction, old: str | None = None, new: str | None = None):
        nonlocal last
        last = created + step * moment
        ticket.history.append(TicketHistory(user=user, action=action, old_value=old, new_value=new, created_at=last))

    def move(moment: int, user: User, new_status: TicketStatus):
        log(moment, user, HistoryAction.STATUS_ALTERADO, ticket.status, new_status)
        ticket.status = new_status

    log(0, requester, HistoryAction.CRIADO, new=TicketStatus.ABERTO)

    passes_through = {E: 1, R: 2, F: 3}.get(spec.status, 3 if spec.reopened else 0)
    if passes_through >= 1:
        ticket.assigned_to = assignee
        log(1, assignee, HistoryAction.ATRIBUIDO, new=assignee.name)
        move(2, assignee, E)
    if passes_through >= 2:
        ticket.solution = spec.solution
        ticket.resolved_at = created + step * 6
        log(6, assignee, HistoryAction.SOLUCAO_REGISTRADA, new=spec.solution)
        move(6, assignee, R)
    if passes_through >= 3:
        ticket.closed_at = created + step * 8
        move(8, requester, F)
    if spec.reopened:
        # Reabrir limpa solução e datas; o valor antigo da solução fica guardado no histórico
        log(9, requester, HistoryAction.REABERTO, F, A)
        ticket.status = A
        ticket.solution = ticket.resolved_at = ticket.closed_at = None
    if spec.archived:
        log(9, users["admin"], HistoryAction.ARQUIVADO)
        ticket.is_archived = True

    for moment, author, message in spec.comments:
        ticket.comments.append(Comment(user=users[author], message=message, created_at=created + step * moment))
        last = max(last, created + step * moment)

    ticket.updated_at = last
    return ticket


def run_seed(db: Session, demo_password: str) -> dict[str, int]:
    """Cria o que estiver faltando e devolve quantos registros de cada tipo existem no final."""
    categories = _ensure_categories(db)
    users = _ensure_users(db, demo_password)
    db.flush()

    if db.scalar(select(func.count()).select_from(Ticket)) == 0:
        now = datetime.now(timezone.utc)
        db.add_all(_build_ticket(spec, users, categories, now) for spec in DEMO_TICKETS)

    db.commit()
    return {
        model.__tablename__: db.scalar(select(func.count()).select_from(model))
        for model in (User, Category, Ticket, Comment, TicketHistory)
    }


def main() -> None:
    demo_password = get_settings().demo_password
    if not demo_password:
        raise SystemExit("Defina DEMO_PASSWORD no .env antes de rodar o seed.")

    with SessionLocal() as db:
        totals = run_seed(db, demo_password)

    print("Seed concluído. Registros no banco:")
    for table, total in totals.items():
        print(f"  {table:<15} {total}")


if __name__ == "__main__":
    main()
