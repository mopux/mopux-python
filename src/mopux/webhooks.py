"""Verify and parse incoming Mopux webhooks."""

from __future__ import annotations

import hmac
import json
import re
import time
from collections.abc import Iterable, Sequence
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, NoReturn, Protocol

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

from .errors import InvalidWebhookPayloadError, InvalidWebhookSignatureError
from .models import TaskDetail

_SIGNATURE = re.compile(r"t=(0|[1-9][0-9]{0,18}),v1=([0-9a-f]{64})")
_UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", re.IGNORECASE | re.ASCII)
_UTC_TIMESTAMP = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z")


def verify_webhook_signature(
    raw_body: bytes, header: str | None, secret: str, *, tolerance: int = 300, now: int | None = None
) -> None:
    """Raise InvalidWebhookSignatureError unless the signature is valid and timely."""
    parts = _SIGNATURE.fullmatch(header or "")
    if parts is None:
        raise InvalidWebhookSignatureError("Malformed Mopux webhook signature header.")

    timestamp = int(parts[1])
    if timestamp > 2**63 - 1:
        raise InvalidWebhookSignatureError("Malformed Mopux webhook signature header.")
    if abs((int(time.time()) if now is None else now) - timestamp) > tolerance:
        raise InvalidWebhookSignatureError("Mopux webhook timestamp is outside the allowed tolerance.")

    expected = hmac.digest(secret.encode(), parts[1].encode() + b"." + raw_body, "sha256").hex()
    if not secret or not hmac.compare_digest(expected, parts[2]):
        raise InvalidWebhookSignatureError("Mopux webhook signature does not match.")


class WebhookEventType(StrEnum):
    TASK_CREATED = "task.created"
    TASK_COMPLETED = "task.completed"
    TASK_STATUS_CHANGED = "task.status_changed"
    TASK_ASSIGNED = "task.assigned"
    TASK_UPDATED = "task.updated"
    TASK_MOVED = "task.moved"
    TASK_DELETED = "task.deleted"
    PING = "ping"


def _read_string(value: object) -> object:
    if type(value) in (int, float):
        return str(value)
    return value


def _read_integer(value: object) -> object:
    if isinstance(value, str) and re.fullmatch(r"-?[0-9]+", value):
        return int(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _read_uuid(value: str) -> str:
    if _UUID.fullmatch(value) is None:
        raise ValueError("Expected a UUID.")
    return value


_WebhookString = Annotated[str, BeforeValidator(_read_string)]
_WebhookInteger = Annotated[int, BeforeValidator(_read_integer)]
_OPTIONAL_INTEGER = TypeAdapter(_WebhookInteger | None, config=ConfigDict(strict=True))
_INTEGER_LIST = TypeAdapter(list[_WebhookInteger], config=ConfigDict(strict=True))


class WebhookActor(BaseModel):
    model_config = ConfigDict(strict=True)

    id: _WebhookInteger
    name: _WebhookString
    via: _WebhookString


class _FieldChange(BaseModel):
    old: Any
    new: Any


_CHANGES = TypeAdapter(dict[str, _FieldChange])


class WebhookEvent(BaseModel):
    """A webhook event envelope with typed accessors for common data fields."""

    model_config = ConfigDict(strict=True)

    id: str
    delivery_id: str
    event: WebhookEventType | str = Field(min_length=1)
    occurred_at: datetime
    installation: _WebhookString
    actor: WebhookActor | None
    data: dict[str, Any]

    _validate_uuid = field_validator("id", "delivery_id")(_read_uuid)

    @field_validator("data", mode="before")
    @classmethod
    def _normalize_empty_data(cls, value: object) -> object:
        # PHP can serialize an empty map as a JSON array.
        return {} if value == [] else value

    @field_validator("occurred_at", mode="before")
    @classmethod
    def _parse_timestamp(cls, value: object) -> datetime:
        if not isinstance(value, str) or _UTC_TIMESTAMP.fullmatch(value) is None:
            raise ValueError("Expected an ISO-8601 timestamp in UTC ending in Z.")
        return datetime.fromisoformat(value)

    @field_validator("event", mode="before")
    @classmethod
    def _parse_event_type(cls, value: object) -> object:
        value = _read_string(value)
        if isinstance(value, str):
            try:
                return WebhookEventType(value)
            except ValueError:
                return value
        return value

    @property
    def task(self) -> TaskDetail | None:
        """Return the task detail. Deleted task data is available in data['task']."""
        task = self.data.get("task")
        if task is None:
            return None
        if not isinstance(task, dict):
            raise InvalidWebhookPayloadError("Expected an object in webhook.data.task.")
        if task.get("deleted") is True:
            return None
        try:
            return TaskDetail.model_validate(task)
        except ValidationError as exc:
            raise InvalidWebhookPayloadError("Invalid webhook.data.task.") from exc

    @property
    def previous_status(self) -> int | None:
        return self._optional_integer("previous_status")

    @property
    def previous_project_id(self) -> int | None:
        return self._optional_integer("previous_project_id")

    @property
    def previous_group_id(self) -> int | None:
        return self._optional_integer("previous_group_id")

    def _optional_integer(self, field: str) -> int | None:
        try:
            return _OPTIONAL_INTEGER.validate_python(self.data.get(field))
        except ValidationError as exc:
            raise InvalidWebhookPayloadError(f"Expected an integer in webhook.data.{field}.") from exc

    @property
    def assigned_user_ids(self) -> list[int]:
        values = self.data.get("assigned_user_ids")
        try:
            return [] if values is None else _INTEGER_LIST.validate_python(values)
        except ValidationError as exc:
            raise InvalidWebhookPayloadError("Expected a list of integers in webhook.data.assigned_user_ids.") from exc

    @property
    def changes(self) -> dict[str, dict[str, Any]]:
        values = self.data.get("changes")
        if values is None or values == []:
            return {}
        try:
            changes = _CHANGES.validate_python(values)
        except ValidationError as exc:
            raise InvalidWebhookPayloadError("Expected a map of old and new values in webhook.data.changes.") from exc
        return {field: {"old": change.old, "new": change.new} for field, change in changes.items()}


def _reject_json_constant(value: str) -> NoReturn:
    raise ValueError(f"Invalid JSON constant: {value}.")


class _Headers(Protocol):
    def items(self) -> Iterable[tuple[str, str | Sequence[str]]]: ...


def parse_webhook_event(raw_body: bytes, headers: _Headers, secret: str) -> WebhookEvent:
    """Verify the raw body, then parse the event and check its delivery headers."""
    normalized: dict[str, list[str]] = {}
    for name, values in headers.items():
        normalized.setdefault(name.lower(), []).extend([values] if isinstance(values, str) else values)

    signatures = normalized.get("x-mopux-signature", [])
    verify_webhook_signature(raw_body, signatures[0] if len(signatures) == 1 else None, secret)

    try:
        payload = json.loads(raw_body.decode(), parse_constant=_reject_json_constant)
    except (ValueError, RecursionError) as exc:
        raise InvalidWebhookPayloadError("Expected a JSON object in the webhook body.") from exc
    if not isinstance(payload, dict):
        raise InvalidWebhookPayloadError("Expected a JSON object in the webhook body.")

    delivery = normalized.get("x-mopux-delivery", [])
    if len(delivery) != 1:
        raise InvalidWebhookPayloadError("Expected a single X-Mopux-Delivery header.")
    try:
        event = WebhookEvent.model_validate({**payload, "delivery_id": delivery[0]})
    except ValidationError as exc:
        raise InvalidWebhookPayloadError("Invalid Mopux webhook envelope.") from exc

    if normalized.get("x-mopux-event") != [event.event]:
        raise InvalidWebhookPayloadError("Expected a single X-Mopux-Event header matching the event in the body.")
    return event
