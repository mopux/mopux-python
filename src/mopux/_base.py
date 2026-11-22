"""Transport-independent pieces shared by the sync and async clients."""

from __future__ import annotations

import json
import platform
import re
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from typing import Any, TypeVar
from urllib.parse import quote, urlsplit

import httpx
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from ._version import __version__
from .errors import (
    SAFE_METHODS,
    ApiError,
    AuthenticationError,
    AuthorizationError,
    ClientError,
    InvalidInputError,
    MalformedResponseError,
    NotFoundError,
    RateLimitError,
    ServerError,
    UncertainWriteError,
    ValidationError,
)

M = TypeVar("M", bound=BaseModel)


class Unset:
    """Marker for "do not send this field" (None means "clear it")."""

    _instance: Unset | None = None

    def __new__(cls) -> Unset:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET = Unset()


def normalize_base_url(base_url: str) -> str:
    parts = urlsplit(base_url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise InvalidInputError("base_url", f'"{base_url}" is not a valid http(s) URL.')
    path = re.sub(r"/api/v1$", "", parts.path.rstrip("/"))
    return f"{parts.scheme}://{parts.netloc}{path}"


def user_agent(extra: str | None) -> str:
    agent = f"mopux-python/{__version__} python/{platform.python_version()}"
    return f"{agent} {extra}" if extra else agent


def build_query(query: Mapping[str, Any]) -> str:
    """Laravel-style query: None dropped, booleans 1/0, lists ``k[]=v``, dicts ``k[sub]=v``."""
    parts: list[str] = []

    def add(key: str, value: Any) -> None:
        if value is None or isinstance(value, Unset):
            return
        if isinstance(value, Mapping):
            for sub, item in value.items():
                add(f"{key}[{sub}]", item)
            return
        if isinstance(value, Sequence) and not isinstance(value, str | bytes):
            for item in value:
                add(f"{key}[]", item)
            return
        if isinstance(value, bool):
            scalar = "1" if value else "0"
        elif isinstance(value, date):
            scalar = value.isoformat()
        else:
            scalar = str(value)
        parts.append(f"{quote(key, safe='')}={quote(scalar, safe='')}")

    for key, value in query.items():
        add(key, value)
    return "&".join(parts)


def compact(**fields: Any) -> dict[str, Any]:
    """Drops UNSET fields; None is kept so the API clears the value."""
    return {key: value for key, value in fields.items() if not isinstance(value, Unset)}


def unwrap(method: str, path: str, response: httpx.Response) -> Any:
    """The ``data`` member of a successful response."""
    raw = response.text
    if not raw.strip():
        return None
    try:
        body = json.loads(raw)
    except ValueError:
        raise MalformedResponseError(method, path, response.status_code, raw, "the body is not JSON") from None
    if not isinstance(body, dict) or "data" not in body:
        raise MalformedResponseError(method, path, response.status_code, raw, 'missing the "data" member')
    return body["data"]


def map_error(method: str, path: str, response: httpx.Response) -> ApiError:
    try:
        body: Any = response.json() if response.text.strip() else None
    except ValueError:
        body = None
    status = response.status_code
    is_write = method.upper() not in SAFE_METHODS
    error_class: type[ApiError]
    if status == 401:
        error_class = AuthenticationError
    elif status == 403:
        error_class = AuthorizationError
    elif status == 404:
        error_class = NotFoundError
    elif status == 422:
        error_class = ValidationError
    elif status == 429:
        error_class = RateLimitError
    elif status >= 500:
        error_class = UncertainWriteError if is_write else ServerError
    else:
        error_class = ClientError
    message = _error_message(status, response.reason_phrase, body)
    if error_class is UncertainWriteError:
        message += " The write outcome is uncertain: refresh the state before retrying."
    return error_class(message, status, method, path, body, response.headers)


def _error_message(status: int, reason: str, body: Any) -> str:
    raw_data = body.get("data") if isinstance(body, dict) else None
    data: dict[str, Any] = raw_data if isinstance(raw_data, dict) else {}
    raw_error = data.get("error")
    error = raw_error.strip() if isinstance(raw_error, str) and raw_error.strip() else None
    raw_message = body.get("message") if isinstance(body, dict) else None
    message = raw_message.strip() if isinstance(raw_message, str) else ""
    if not message:
        message = error or reason or "Mopux API error"
    details = _validation_messages(data.get("errors")) if status == 422 else ([error] if error else [])
    for detail in dict.fromkeys(details):
        if detail not in message:
            message += f" {detail}"
    return f"{message} (HTTP {status})"


def _validation_messages(errors: Any) -> list[str]:
    messages: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str) and value.strip():
            messages.append(value.strip())
        elif isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)

    walk(errors)
    return messages


def validator(model: type[M]) -> Callable[[Any], M]:
    """Validates API data into ``model``; unexpected data raises MalformedResponseError, not a pydantic error."""

    def validate(data: Any) -> M:
        try:
            return model.model_validate(data if data is not None else {})
        except PydanticValidationError as error:
            raw = json.dumps(data, default=str)[:2000]
            raise MalformedResponseError("-", model.__name__, 200, raw, str(error)) from error

    return validate


def parse(model: type[M], data: Any) -> M:
    return validator(model)(data)


def parse_list(model: type[M], data: Any) -> list[M]:
    validate = validator(model)
    return [validate(item) for item in data] if isinstance(data, list) else []
