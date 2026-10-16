from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# O .env fica na raiz do repositório (helpboard/.env), compartilhado com o docker-compose.
ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    database_url: str
    test_database_url: str | None = None
    secret_key: str
    # Senha dos usuários de demonstração criados pelo seed
    demo_password: str | None = None
    access_token_expire_minutes: int = 60
    cors_origins: str = ""
    # Fuso usado para interpretar os filtros por dia (o banco guarda tudo em UTC)
    timezone: str = "America/Sao_Paulo"
    # Chamado RESOLVIDO há mais que isso sem o solicitante aceitar nem recusar é fechado sozinho (0 desliga)
    auto_close_days: int = Field(default=7, ge=0)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
