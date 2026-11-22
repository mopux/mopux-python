"""Testing helpers: a fake Mopux API on top of ``httpx.MockTransport``.

```python
from mopux import Mopux
from mopux.testing import MockApi

api = MockApi().push(MockApi.json([{"id": 1, "title": "Review"}]))
mopux = Mopux("https://acme.test", "token", http_client=api.client())
mopux.tasks.my()
api.assert_sent("GET", "tasks/my")
```
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

Responder = httpx.Response | Exception | Callable[["RecordedRequest"], "httpx.Response | Exception"]


@dataclass
class RecordedRequest:
    method: str
    url: httpx.URL
    path: str
    """Path relative to ``/api/v1/``, e.g. ``tasks/12``."""
    headers: httpx.Headers
    content: bytes

    @property
    def json(self) -> Any:
        return json.loads(self.content) if self.content else None


class MockApi:
    """Answers requests from a queue and records them."""

    def __init__(self) -> None:
        self.requests: list[RecordedRequest] = []
        self._queue: list[Responder] = []
        self._fallback: Responder | None = None
        self.transport = httpx.MockTransport(self._handle)
        self.async_transport = httpx.MockTransport(self._handle)

    def client(self) -> httpx.Client:
        """An ``httpx.Client`` to pass as ``http_client`` to :class:`mopux.Mopux`."""
        return httpx.Client(transport=self.transport)

    def async_client(self) -> httpx.AsyncClient:
        """An ``httpx.AsyncClient`` to pass as ``http_client`` to :class:`mopux.AsyncMopux`."""
        return httpx.AsyncClient(transport=self.async_transport)

    def push(self, *responders: Responder) -> MockApi:
        """Queues responses (or exceptions such as ``httpx.ConnectError``), answered in order."""
        self._queue.extend(responders)
        return self

    def always(self, responder: Responder) -> MockApi:
        """Answers every request without a queued response."""
        self._fallback = responder
        return self

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path = urlsplit(str(request.url)).path
        recorded = RecordedRequest(
            method=request.method,
            url=request.url,
            path=path.split("/api/v1/", 1)[1] if "/api/v1/" in path else path.lstrip("/"),
            headers=request.headers,
            content=request.read(),
        )
        self.requests.append(recorded)
        responder = self._queue.pop(0) if self._queue else self._fallback
        if responder is None:
            raise AssertionError(f"MockApi: no response queued for {recorded.method} {recorded.path}")
        result = responder(recorded) if callable(responder) else responder
        if isinstance(result, Exception):
            raise result
        return result

    @staticmethod
    def json(data: Any, status: int = 200, headers: Mapping[str, str] | None = None) -> httpx.Response:
        """A success response with the Mopux envelope."""
        return httpx.Response(status, json={"success": True, "message": "OK", "data": data}, headers=headers)

    @staticmethod
    def error(
        status: int, message: str, data: Mapping[str, Any] | None = None, headers: Mapping[str, str] | None = None
    ) -> httpx.Response:
        """An error response with the Mopux envelope."""
        body = {"success": False, "message": message, "data": {"error": message, **(data or {})}}
        return httpx.Response(status, json=body, headers=headers)

    @staticmethod
    def plan_restricted(feature: str = "api") -> httpx.Response:
        """403 returned when the installation plan does not include a feature."""
        return MockApi.error(
            403,
            "The plan of this installation does not include this feature.",
            {"code": "plan_feature_unavailable", "feature": feature},
        )

    @staticmethod
    def validation(errors: Mapping[str, list[str]]) -> httpx.Response:
        return MockApi.error(422, "The given data was invalid.", {"errors": dict(errors)})

    @staticmethod
    def network_error(message: str = "connection refused") -> httpx.ConnectError:
        return httpx.ConnectError(message)

    def assert_sent(
        self, method: str, path: str, match: Callable[[RecordedRequest], bool] | None = None
    ) -> RecordedRequest:
        """Raises AssertionError unless a request with this method and path was sent."""
        for request in self.requests:
            if request.method == method.upper() and request.path == path and (match is None or match(request)):
                return request
        sent = ", ".join(f"{request.method} {request.path}" for request in self.requests) or "none"
        raise AssertionError(f"MockApi: expected {method.upper()} {path} to be sent. Sent: {sent}")

    def assert_nothing_sent(self) -> None:
        if self.requests:
            raise AssertionError(f"MockApi: expected no requests, {len(self.requests)} sent.")
