from math import ceil
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, computed_field

T = TypeVar("T")


class ErrorOut(BaseModel):
    """Formato das respostas de erro de regra de negócio."""

    detail: str


class Page(BaseModel, Generic[T]):
    """Uma página de resultados e o total geral, para o frontend montar a paginação."""

    items: list[T]
    total: int
    page: int
    page_size: int

    @computed_field
    @property
    def pages(self) -> int:
        return ceil(self.total / self.page_size)


_ERROR_DESCRIPTIONS = {
    401: "Não autenticado (sem token, token inválido ou expirado)",
    403: "Perfil sem permissão para a ação",
    404: "Não encontrado (ou fora do que o usuário pode ver)",
    409: "Regra de negócio violada",
}


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    """Documenta no Swagger os erros que uma rota pode devolver."""
    return {code: {"model": ErrorOut, "description": _ERROR_DESCRIPTIONS[code]} for code in codes}
