# Generated from src/mopux/_async by scripts/unasync.py. Do not edit.
from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from .._base import build_query, map_error, normalize_base_url, unwrap, user_agent
from .._retry import RetryPolicy
from ..errors import MopuxConnectionError

TokenSource = str | Callable[[], str | None] | None


class Connector:
    """Sends requests to ``/api/v1``, unwraps ``{success, message, data}`` and raises typed errors."""

    def __init__(
        self,
        base_url: str,
        token: TokenSource = None,
        *,
        timeout: float = 30.0,
        retry: RetryPolicy | None = None,
        user_agent_suffix: str | None = None,
        headers: Mapping[str, str] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self.token = token
        self.timeout = timeout
        self.retry = retry or RetryPolicy()
        self.user_agent_suffix = user_agent_suffix
        self.headers = dict(headers or {})
        self._owns_client = http_client is None
        self.http = http_client or httpx.Client(timeout=timeout)

    def with_token(self, token: TokenSource) -> Connector:
        """A connector for the same installation and HTTP client with another token."""
        connector = Connector(
            self.base_url,
            token,
            timeout=self.timeout,
            retry=self.retry,
            user_agent_suffix=self.user_agent_suffix,
            headers=self.headers,
            http_client=self.http,
        )
        connector._owns_client = False
        return connector

    def close(self) -> None:
        if self._owns_client:
            self.http.close()

    def get(self, path: str, query: Mapping[str, Any] | None = None) -> Any:
        return self.request("GET", path, query=query)

    def post(self, path: str, json: Any = None) -> Any:
        return self.request("POST", path, json=json)

    def patch(self, path: str, json: Any = None) -> Any:
        return self.request("PATCH", path, json=json)

    def delete(self, path: str, query: Mapping[str, Any] | None = None, json: Any = None) -> Any:
        return self.request("DELETE", path, query=query, json=json)

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Mapping[str, Any] | None = None,
        json: Any = None,
        data: Mapping[str, Any] | None = None,
        files: list[tuple[str, tuple[str, bytes, str]]] | None = None,
    ) -> Any:
        method = method.upper()
        path = path.lstrip("/")
        query_string = build_query(query or {})
        url = f"{self.base_url}/api/v1/{path}" + (f"?{query_string}" if query_string else "")
        headers = {**self.headers, "Accept": "application/json", "User-Agent": user_agent(self.user_agent_suffix)}
        token = self.token() if callable(self.token) else self.token
        if token:
            headers["Authorization"] = f"Bearer {token}"

        attempt = 0
        while True:
            try:
                response = self.http.request(
                    method,
                    url,
                    headers=headers,
                    json=json if files is None else None,
                    data=data if files is not None else None,
                    files=files,
                    timeout=self.timeout,
                )
            except httpx.TransportError as error:
                delay = self.retry.delay_after_connection_error(method, attempt)
                if delay is None:
                    raise MopuxConnectionError(method, path, error) from error
                time.sleep(delay)
                attempt += 1
                continue

            if response.is_success:
                return unwrap(method, path, response)

            delay = self.retry.delay_after_response(
                method, response.status_code, response.headers.get("retry-after"), attempt
            )
            if delay is not None:
                time.sleep(delay)
                attempt += 1
                continue

            raise map_error(method, path, response)
