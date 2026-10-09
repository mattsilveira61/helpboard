from enum import StrEnum

# Os códigos não têm acento para evitar problemas de encoding em URLs, filtros e no banco.
# Os textos com acento ("Crítica", "Em andamento"...) ficam por conta do frontend.


class Role(StrEnum):
    ADMIN = "ADMIN"
    TECNICO = "TECNICO"
    SOLICITANTE = "SOLICITANTE"


class TicketStatus(StrEnum):
    ABERTO = "ABERTO"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    RESOLVIDO = "RESOLVIDO"
    FECHADO = "FECHADO"


class Priority(StrEnum):
    CRITICA = "CRITICA"
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAIXA = "BAIXA"


class HistoryAction(StrEnum):
    CRIADO = "CRIADO"
    EDITADO = "EDITADO"
    STATUS_ALTERADO = "STATUS_ALTERADO"
    ATRIBUIDO = "ATRIBUIDO"
    PRIORIDADE_ALTERADA = "PRIORIDADE_ALTERADA"
    CATEGORIA_ALTERADA = "CATEGORIA_ALTERADA"
    SOLUCAO_REGISTRADA = "SOLUCAO_REGISTRADA"
    REABERTO = "REABERTO"
    ARQUIVADO = "ARQUIVADO"
