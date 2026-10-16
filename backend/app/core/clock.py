"""Data e hora da aplicação. O banco guarda tudo em UTC; os "dias" seguem o fuso da empresa (setting TIMEZONE)."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def now() -> datetime:
    return datetime.now(UTC)


def company_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def today() -> date:
    """O dia de hoje no calendário da empresa (às 22h em São Paulo, em UTC já é amanhã)."""
    return now().astimezone(company_tz()).date()


def start_of_day(day: date) -> datetime:
    """Meia-noite do dia no fuso da empresa, para os filtros por período baterem com o calendário do usuário."""
    return datetime.combine(day, time.min, tzinfo=company_tz())
