"""Official Python SDK for the Mopux API."""

from ._async.client import AsyncMopux
from ._async.connector import AsyncConnector
from ._base import UNSET, Unset
from ._retry import RetryPolicy
from ._sync.client import Mopux
from ._sync.connector import Connector
from ._version import __version__
from .errors import (
    ApiError,
    AuthenticationError,
    AuthorizationError,
    ClientError,
    InvalidInputError,
    InvalidWebhookPayloadError,
    InvalidWebhookSignatureError,
    MalformedResponseError,
    MopuxConnectionError,
    MopuxError,
    NotFoundError,
    RateLimitError,
    ServerError,
    UncertainWriteError,
    ValidationError,
)
from .page import Page
from .upload import Upload
from .webhooks import WebhookActor, WebhookEvent, WebhookEventType, parse_webhook_event, verify_webhook_signature

TaskStatuses = {"pending": 0, "in_progress": 1, "review": 2, "done": 3}
TaskPriorities = {"low": 0, "normal": 1, "high": 2, "maximum": 9}

__all__ = [
    "UNSET",
    "ApiError",
    "AsyncConnector",
    "AsyncMopux",
    "AuthenticationError",
    "AuthorizationError",
    "ClientError",
    "Connector",
    "InvalidInputError",
    "InvalidWebhookPayloadError",
    "InvalidWebhookSignatureError",
    "MalformedResponseError",
    "Mopux",
    "MopuxConnectionError",
    "MopuxError",
    "NotFoundError",
    "Page",
    "RateLimitError",
    "RetryPolicy",
    "ServerError",
    "TaskPriorities",
    "TaskStatuses",
    "UncertainWriteError",
    "Unset",
    "Upload",
    "ValidationError",
    "WebhookActor",
    "WebhookEvent",
    "WebhookEventType",
    "__version__",
    "parse_webhook_event",
    "verify_webhook_signature",
]
