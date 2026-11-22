from __future__ import annotations

import random
from dataclasses import dataclass

from .errors import SAFE_METHODS, InvalidInputError, parse_retry_after


@dataclass(frozen=True)
class RetryPolicy:
    """Reads are retried on network errors and 5xx; any method is retried on 429 when the API says
    how long to wait. Writes are never retried after a network error or a 5xx."""

    max_retries: int = 2
    base_delay: float = 0.25
    max_delay: float = 5.0
    max_retry_after: int = 60

    def __post_init__(self) -> None:
        for name in ("max_retries", "base_delay", "max_delay", "max_retry_after"):
            if getattr(self, name) < 0:
                raise InvalidInputError(f"retry.{name}", "cannot be negative.")

    @classmethod
    def none(cls) -> RetryPolicy:
        return cls(max_retries=0)

    def delay_after_connection_error(self, method: str, attempt: int) -> float | None:
        if attempt >= self.max_retries or method.upper() not in SAFE_METHODS:
            return None
        return self._backoff(attempt)

    def delay_after_response(self, method: str, status: int, retry_after: str | None, attempt: int) -> float | None:
        if attempt >= self.max_retries:
            return None
        if status == 429:
            seconds = parse_retry_after(retry_after)
            if seconds is None:
                return self._backoff(attempt)
            return float(seconds) if seconds <= self.max_retry_after else None
        if status >= 500 and method.upper() in SAFE_METHODS:
            return self._backoff(attempt)
        return None

    def _backoff(self, attempt: int) -> float:
        delay = min(self.max_delay, self.base_delay * (2.0**attempt))
        return min(self.max_delay, delay + random.uniform(0, delay / 4))
