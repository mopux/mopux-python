import hmac
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from mopux import (
    InvalidWebhookPayloadError,
    InvalidWebhookSignatureError,
    WebhookEventType,
    parse_webhook_event,
    verify_webhook_signature,
)
from mopux.models import TaskDetail

_FIXTURES = Path(__file__).parent / "fixtures" / "webhooks"
_VECTORS = json.loads((_FIXTURES / "signature-vectors.json").read_text())["vectors"]
_EVENTS = json.loads((_FIXTURES / "events.json").read_text())
_TASK = json.loads((_FIXTURES / "task_detail.json").read_text())
_DELIVERY = "00000000-0000-4000-8000-000000000002"
_NOW = 1_800_000_000


@pytest.fixture(autouse=True)
def freeze_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("mopux.webhooks.time.time", lambda: _NOW)


def _signed_headers(body: bytes, event: str = "ping", secret: str = "test") -> dict[str, str]:
    signature = hmac.digest(secret.encode(), str(_NOW).encode() + b"." + body, "sha256").hex()
    return {
        "x-MoPuX-SiGnAtUrE": f"t={_NOW},v1={signature}",
        "X-Mopux-Event": event,
        "X-Mopux-Delivery": _DELIVERY,
    }


@pytest.mark.parametrize("vector", _VECTORS)
def test_signature_vectors(vector: dict[str, Any]) -> None:
    body = vector["body"].encode()
    header = vector["signature"]
    secret = vector["secret"]
    timestamp = vector["timestamp"]

    for offset in (0, -300, 300):
        verify_webhook_signature(body, header, secret, now=timestamp + offset)
    for offset in (-301, 301):
        with pytest.raises(InvalidWebhookSignatureError, match="outside"):
            verify_webhook_signature(body, header, secret, now=timestamp + offset)
    with pytest.raises(InvalidWebhookSignatureError, match="does not match"):
        verify_webhook_signature(body + b"\n", header, secret, now=timestamp)
    with pytest.raises(InvalidWebhookSignatureError, match="does not match"):
        verify_webhook_signature(body, header, secret + "x", now=timestamp)
    verify_webhook_signature(body, header, secret, tolerance=301, now=timestamp + 301)


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "v1=abc",
        "t=123,v1=abc",
        "t=1,t=2,v1=" + "0" * 64,
        "t=9223372036854775808,v1=" + "0" * 64,
        "t=01,v1=" + "0" * 64,
        "t=-1,v1=" + "0" * 64,
        "t=1,v1=" + "A" * 64,
        "t=1,v1=" + "0" * 64 + "\n",
    ],
)
def test_malformed_signature_headers(header: str | None) -> None:
    with pytest.raises(InvalidWebhookSignatureError, match="Malformed"):
        verify_webhook_signature(b"{}", header, "test")


def test_empty_secret_is_rejected() -> None:
    body = b"{}"
    with pytest.raises(InvalidWebhookSignatureError, match="does not match"):
        verify_webhook_signature(body, _signed_headers(body, secret="")["x-MoPuX-SiGnAtUrE"], "")


@pytest.mark.parametrize("name", _EVENTS["events"])
def test_parse_events(name: str) -> None:
    data = dict(_EVENTS["events"][name])
    if name.startswith("task.") and name != "task.deleted":
        data["task"] = _TASK
    envelope = {**_EVENTS["envelope"], "event": name, "data": data}
    if name == "ping":
        envelope["actor"] = None
    body = json.dumps(envelope, ensure_ascii=False).encode()
    event = parse_webhook_event(body, _signed_headers(body, name), "test")

    assert event.event == name
    assert type(event.event) is (str if name == "project.created" else WebhookEventType)
    assert event.id == envelope["id"]
    assert event.delivery_id == _DELIVERY
    assert event.occurred_at == datetime(2026, 11, 23, 12, 30, 0, 123456, tzinfo=UTC)
    assert event.installation == envelope["installation"]
    assert (event.actor.model_dump() if event.actor else None) == envelope["actor"]
    assert event.data == data
    if data.get("task") == _TASK:
        assert isinstance(event.task, TaskDetail)
        assert event.task.id == _TASK["id"]
    else:
        assert event.task is None
    assert event.previous_status == data.get("previous_status")
    assert event.changes == data.get("changes", {})
    assert event.assigned_user_ids == data.get("assigned_user_ids", [])
    assert event.previous_project_id == data.get("previous_project_id")
    assert event.previous_group_id == data.get("previous_group_id")


def test_reduced_task_is_detected_by_payload() -> None:
    data = _EVENTS["events"]["task.deleted"]
    body = json.dumps({**_EVENTS["envelope"], "event": "task.updated", "data": data}).encode()
    event = parse_webhook_event(body, _signed_headers(body, "task.updated"), "test")
    assert event.task is None
    assert event.data == data


def test_signature_is_verified_before_json() -> None:
    body = b"{"
    headers = _signed_headers(body)
    with pytest.raises(InvalidWebhookSignatureError):
        parse_webhook_event(body, headers, "wrong")
    with pytest.raises(InvalidWebhookPayloadError):
        parse_webhook_event(body, headers, "test")


@pytest.mark.parametrize(
    "overrides",
    [
        {"id": "invalid"},
        {"id": _DELIVERY.replace("-", "")},
        {"occurred_at": "2026-11-23T12:30:00+00:00"},
        {"occurred_at": "2026-02-30T12:30:00Z"},
        {"occurred_at": "2026-11-23T12:30:00Z\n"},
        {"actor": {"id": True, "name": "Ada", "via": "api"}},
        {"actor": {"id": 8, "name": "Ada"}},
        {"data": [1]},
        {"event": ""},
    ],
)
def test_invalid_envelope(overrides: dict[str, Any]) -> None:
    body = json.dumps({**_EVENTS["envelope"], "event": "ping", "data": {}, **overrides}).encode()
    with pytest.raises(InvalidWebhookPayloadError):
        parse_webhook_event(body, _signed_headers(body, overrides.get("event", "ping")), "test")


def test_actor_is_required() -> None:
    envelope = {**_EVENTS["envelope"], "event": "ping", "data": {}}
    del envelope["actor"]
    body = json.dumps(envelope).encode()
    with pytest.raises(InvalidWebhookPayloadError):
        parse_webhook_event(body, _signed_headers(body), "test")


@pytest.mark.parametrize("data", [[], {"changes": []}])
def test_empty_maps_encoded_as_arrays(data: object) -> None:
    body = json.dumps({**_EVENTS["envelope"], "event": "task.updated", "data": data}).encode()
    event = parse_webhook_event(body, _signed_headers(body, "task.updated"), "test")
    assert event.data == (data or {})
    assert event.changes == {}


@pytest.mark.parametrize(
    ("extra_headers", "error"),
    [
        ({"X-MOPUX-SIGNATURE": "extra"}, InvalidWebhookSignatureError),
        ({"x-mopux-event": "ping"}, InvalidWebhookPayloadError),
        ({"X-Mopux-Event": "task.created"}, InvalidWebhookPayloadError),
        ({"X-Mopux-Event": []}, InvalidWebhookPayloadError),
        ({"X-Mopux-Delivery": "bad-id"}, InvalidWebhookPayloadError),
        ({"X-Mopux-Delivery": []}, InvalidWebhookPayloadError),
        ({"X-Mopux-Delivery": [_DELIVERY, _DELIVERY]}, InvalidWebhookPayloadError),
    ],
)
def test_invalid_headers(extra_headers: dict[str, Any], error: type[Exception]) -> None:
    body = json.dumps({**_EVENTS["envelope"], "event": "ping", "data": {}}).encode()
    with pytest.raises(error):
        parse_webhook_event(body, {**_signed_headers(body), **extra_headers}, "test")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("task", []),
        ("previous_status", True),
        ("previous_project_id", "invalid"),
        ("previous_group_id", 2.5),
        ("assigned_user_ids", [8, False]),
        ("changes", {"title": {"new": "After"}}),
    ],
)
def test_invalid_data_is_reported_when_accessed(field: str, value: object) -> None:
    body = json.dumps({**_EVENTS["envelope"], "event": "ping", "data": {field: value}}).encode()
    event = parse_webhook_event(body, _signed_headers(body), "test")
    assert event.data[field] == value
    with pytest.raises(InvalidWebhookPayloadError, match=field):
        getattr(event, field)
