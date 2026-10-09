"""Erros de regra de negócio.

Os services lançam estas exceções sem saber nada de HTTP; o handler registrado no main.py
transforma cada uma na resposta com o status code correspondente.
"""


class AppError(Exception):
    status_code = 400

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class UnauthorizedError(AppError):
    """Não autenticado: sem token, token inválido/vencido ou login incorreto."""

    status_code = 401


class ForbiddenError(AppError):
    """Autenticado, mas o perfil não tem permissão para a ação."""

    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    """A ação viola uma regra de negócio (e-mail repetido, transição de status inválida...)."""

    status_code = 409
