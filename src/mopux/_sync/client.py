# Generated from src/mopux/_async by scripts/unasync.py. Do not edit.
from __future__ import annotations

from collections.abc import Mapping
from types import TracebackType

import httpx

from .._retry import RetryPolicy
from .connector import Connector, TokenSource
from .resources import (
    Auth,
    Comments,
    Notifications,
    Projects,
    TaskGroups,
    Tasks,
    Team,
    TeamInvitations,
    Touches,
)


class Mopux:
    """Client of one Mopux installation.

    Use it as a context manager (``with Mopux(...) as mopux:``) or call ``close()``
    to release the HTTP connections.
    """

    def __init__(
        self,
        base_url: str | Connector,
        token: TokenSource = None,
        *,
        timeout: float = 30.0,
        retry: RetryPolicy | None = None,
        user_agent: str | None = None,
        headers: Mapping[str, str] | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        if isinstance(base_url, Connector):
            self.connector = base_url
        else:
            self.connector = Connector(
                base_url,
                token,
                timeout=timeout,
                retry=retry,
                user_agent_suffix=user_agent,
                headers=headers,
                http_client=http_client,
            )
        self.auth = Auth(self.connector)
        self.projects = Projects(self.connector)
        self.task_groups = TaskGroups(self.connector)
        self.tasks = Tasks(self.connector)
        self.comments = Comments(self.connector)
        self.notifications = Notifications(self.connector)
        self.touches = Touches(self.connector)
        self.team = Team(self.connector)
        self.team_invitations = TeamInvitations(self.connector)

    @classmethod
    def login(
        cls,
        base_url: str,
        email: str,
        password: str,
        *,
        token_name: str | None = None,
        timeout: float = 30.0,
        retry: RetryPolicy | None = None,
        user_agent: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> Mopux:
        """Logs in and returns a client that uses the new token (``client.token``)."""
        anonymous = cls(base_url, timeout=timeout, retry=retry, user_agent=user_agent, http_client=http_client)
        result = anonymous.auth.login(email, password, token_name)
        return cls(anonymous.connector.with_token(result.token or ""))

    @property
    def token(self) -> str | None:
        token = self.connector.token
        return token() if callable(token) else token

    def with_token(self, token: TokenSource) -> Mopux:
        """A client for the same installation (sharing the HTTP connections) with another token."""
        return Mopux(self.connector.with_token(token))

    def close(self) -> None:
        self.connector.close()

    def __enter__(self) -> Mopux:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
