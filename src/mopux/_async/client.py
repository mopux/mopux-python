from __future__ import annotations

from collections.abc import Mapping
from types import TracebackType

import httpx

from .._retry import RetryPolicy
from .connector import AsyncConnector, TokenSource
from .resources import (
    AsyncAuth,
    AsyncComments,
    AsyncNotifications,
    AsyncProjects,
    AsyncTaskGroups,
    AsyncTasks,
    AsyncTeam,
    AsyncTeamInvitations,
    AsyncTouches,
)


class AsyncMopux:
    """Client of one Mopux installation.

    Use it as a context manager (``async with AsyncMopux(...) as mopux:``) or call ``aclose()``
    to release the HTTP connections.
    """

    def __init__(
        self,
        base_url: str | AsyncConnector,
        token: TokenSource = None,
        *,
        timeout: float = 30.0,
        retry: RetryPolicy | None = None,
        user_agent: str | None = None,
        headers: Mapping[str, str] | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if isinstance(base_url, AsyncConnector):
            self.connector = base_url
        else:
            self.connector = AsyncConnector(
                base_url,
                token,
                timeout=timeout,
                retry=retry,
                user_agent_suffix=user_agent,
                headers=headers,
                http_client=http_client,
            )
        self.auth = AsyncAuth(self.connector)
        self.projects = AsyncProjects(self.connector)
        self.task_groups = AsyncTaskGroups(self.connector)
        self.tasks = AsyncTasks(self.connector)
        self.comments = AsyncComments(self.connector)
        self.notifications = AsyncNotifications(self.connector)
        self.touches = AsyncTouches(self.connector)
        self.team = AsyncTeam(self.connector)
        self.team_invitations = AsyncTeamInvitations(self.connector)

    @classmethod
    async def login(
        cls,
        base_url: str,
        email: str,
        password: str,
        *,
        token_name: str | None = None,
        timeout: float = 30.0,
        retry: RetryPolicy | None = None,
        user_agent: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> AsyncMopux:
        """Logs in and returns a client that uses the new token (``client.token``)."""
        anonymous = cls(base_url, timeout=timeout, retry=retry, user_agent=user_agent, http_client=http_client)
        result = await anonymous.auth.login(email, password, token_name)
        return cls(anonymous.connector.with_token(result.token or ""))

    @property
    def token(self) -> str | None:
        token = self.connector.token
        return token() if callable(token) else token

    def with_token(self, token: TokenSource) -> AsyncMopux:
        """A client for the same installation (sharing the HTTP connections) with another token."""
        return AsyncMopux(self.connector.with_token(token))

    async def aclose(self) -> None:
        await self.connector.aclose()

    async def __aenter__(self) -> AsyncMopux:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()
