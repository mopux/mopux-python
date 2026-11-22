"""Errors raised by the SDK. Every one extends :class:`MopuxError`."""

from __future__ import annotations

import email.utils
import time
from typing import Any

import httpx

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class MopuxError(Exception):
    """Base class of every error raised by the SDK."""


class MopuxConnectionError(MopuxError):
    """The request never got an HTTP response (DNS, TLS, timeout, connection reset…)."""

    def __init__(self, method: str, path: str, cause: BaseException) -> None:
        super().__init__(f"Could not reach the Mopux API ({method} {path}): {cause}")
        self.method = method
        self.path = path
        self.__cause__ = cause

    @property
    def is_write_outcome_uncertain(self) -> bool:
        """True for writes: the change may have been applied. Check before sending it again."""
        return self.method.upper() not in SAFE_METHODS


class ApiError(MopuxError):
    """The API answered with a non-2xx status."""

    def __init__(
        self,
        message: str,
        status: int,
        method: str,
        path: str,
        body: Any,
        headers: httpx.Headers | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.method = method
        self.path = path
        self.body = body
        self.headers = headers or httpx.Headers()

    @property
    def _data(self) -> dict[str, Any]:
        data = self.body.get("data") if isinstance(self.body, dict) else None
        return data if isinstance(data, dict) else {}

    @property
    def code(self) -> str | None:
        """Stable machine code from ``data.code`` (e.g. ``plan_feature_unavailable``), if any."""
        code = self._data.get("code")
        return code if isinstance(code, str) else None

    @property
    def api_message(self) -> str | None:
        """The API message (``message``, or ``data.error`` when there is no message)."""
        if isinstance(self.body, dict) and isinstance(self.body.get("message"), str) and self.body["message"].strip():
            return str(self.body["message"])
        error = self._data.get("error")
        return error if isinstance(error, str) else None


class AuthenticationError(ApiError):
    """401: missing, invalid, revoked or expired token. Log in again."""


class AuthorizationError(ApiError):
    """403: no permission, missing OAuth scope, plan restriction or blocked billing."""

    def is_plan_restriction(self) -> bool:
        """The installation plan does not include the feature."""
        return self.code == "plan_feature_unavailable"

    @property
    def plan_feature(self) -> str | None:
        """The feature the plan lacks (e.g. ``api``) when the error is a plan restriction."""
        feature = self._data.get("feature")
        return feature if self.is_plan_restriction() and isinstance(feature, str) else None

    def is_billing_blocked(self) -> bool:
        """The installation is blocked by billing or its public trial has ended."""
        return self.code == "billing_access_blocked"


class NotFoundError(ApiError):
    """404."""


class ValidationError(ApiError):
    """422: the API rejected the input."""

    @property
    def errors(self) -> dict[str, list[str]]:
        """Messages per field, from ``data.errors``."""
        raw = self._data.get("errors")
        if not isinstance(raw, dict):
            return {}
        result: dict[str, list[str]] = {}
        for field, messages in raw.items():
            items = messages if isinstance(messages, list) else [messages]
            result[str(field)] = [message for message in items if isinstance(message, str)]
        return result


class RateLimitError(ApiError):
    """429: too many requests."""

    @property
    def retry_after(self) -> int | None:
        """Seconds to wait, from ``Retry-After``."""
        return parse_retry_after(self.headers.get("retry-after"))


class ServerError(ApiError):
    """5xx on a read. Safe to retry later."""


class UncertainWriteError(ApiError):
    """5xx on a write: the change may or may not have been applied. Check before retrying."""


class ClientError(ApiError):
    """Any other 4xx."""


class MalformedResponseError(MopuxError):
    """The API answered 2xx with a body the SDK cannot understand."""

    def __init__(self, method: str, path: str, status: int, raw_body: str, reason: str) -> None:
        super().__init__(f"Malformed response from the Mopux API ({method} {path}, HTTP {status}): {reason}")
        self.method = method
        self.path = path
        self.status = status
        self.raw_body = raw_body


class InvalidInputError(MopuxError, ValueError):
    """The SDK rejected an argument before sending the request."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"Invalid {field}: {reason}")
        self.field = field
        self.reason = reason


def parse_retry_after(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    value = value.strip()
    if value.isdigit():
        return int(value)
    try:
        moment = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    return max(0, int(moment.timestamp() - time.time() + 0.999))
