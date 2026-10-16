"""Limite de tentativas de login erradas, para dificultar quem tenta adivinhar senhas.

Fica na memória do processo: basta para a API rodando numa instância só. Com várias instâncias,
cada uma teria o próprio contador, e o caminho seria guardar as tentativas num Redis.
"""

import math
import time
from collections import deque
from collections.abc import Callable
from threading import Lock


class LoginLimiter:
    def __init__(self, max_failures: int = 5, window_seconds: float = 60, clock: Callable[[], float] = time.monotonic):
        self.max_failures = max_failures
        self.window = window_seconds
        self.clock = clock
        self._failures: dict[tuple[str, str], deque[float]] = {}
        self._lock = Lock()

    def _recent(self, key: tuple[str, str], now: float) -> deque[float]:
        """Erros da chave ainda dentro da janela (os mais antigos são descartados)."""
        failures = self._failures.get(key, deque())
        while failures and failures[0] <= now - self.window:
            failures.popleft()
        if not failures:
            self._failures.pop(key, None)
        return failures

    def retry_after(self, ip: str, email: str) -> int:
        """Segundos até poder tentar de novo; 0 quando a tentativa está liberada."""
        key = (ip, email.lower())
        with self._lock:
            now = self.clock()
            failures = self._recent(key, now)
            if len(failures) < self.max_failures:
                return 0
            return max(1, math.ceil(failures[0] + self.window - now))

    def fail(self, ip: str, email: str) -> None:
        key = (ip, email.lower())
        with self._lock:
            now = self.clock()
            failures = self._recent(key, now)
            failures.append(now)
            self._failures[key] = failures

    def reset(self, ip: str, email: str) -> None:
        with self._lock:
            self._failures.pop((ip, email.lower()), None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()

login_limiter = LoginLimiter()
