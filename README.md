# Mopux Python

Official Python client for the [Mopux](https://www.mopux.com) API (`/api/v1`).

- Every API operation covered (71/71), checked against the OpenAPI spec in CI.
- Sync (`Mopux`) and async (`AsyncMopux`) clients with the same API, built on `httpx`.
- Typed `pydantic` models generated from the OpenAPI spec; unknown fields are kept, so a newer API does not break the client.
- Safe by default: retries rate-limited requests and failed reads, **never** retries a write whose outcome is unknown.
- `MockApi` testing helper in `mopux.testing`.

## Requirements

Python 3.11 to 3.14. Only Python versions that still receive security fixes are supported.

## Installation

```bash
pip install mopux
```

## Quick start

```python
from mopux import Mopux

with Mopux("https://acme.mopux.com", token) as mopux:
    board = mopux.projects.board(12)
    for group in board.task_groups or []:
        print(f"{group.title}: {len(group.tasks or [])} open tasks")

    task = mopux.tasks.create(
        12,  # project id
        7,  # group id
        "Write the release notes",
        priority=2,
        hours_expected="2:30",
        assignees=[3, 5],
    )
    mopux.tasks.update_status(task.id, 3)
```

Async:

```python
from mopux import AsyncMopux

async with AsyncMopux("https://acme.mopux.com", token) as mopux:
    tasks = await mopux.tasks.my()
    async for project in mopux.projects.iter():
        print(project.title)
```

## Authentication

The base URL is your Mopux installation (each installation has its own domain). The client adds `/api/v1/` itself.

**Personal access token.** Exchange credentials once and store the token (the API only shows it once):

```python
mopux = Mopux.login("https://acme.mopux.com", email, password, token_name="my-app")
save_secret(mopux.token)
```

Later:

```python
mopux = Mopux("https://acme.mopux.com", token)
mopux.auth.user()  # the token's user
mopux.auth.logout()  # revokes the token
```

`token` also accepts a function called before every request (for tokens kept in a vault or refreshed elsewhere).

Each login creates a new token. List and revoke the user's API tokens; secrets are never returned:

```python
for api_token in mopux.auth.tokens.list():
    print(api_token.id, api_token.name, "(this client)" if api_token.current else "")
mopux.auth.tokens.delete(leaked_token_id)
```

Changing or resetting the password revokes every token of the user, and API tokens unused for 90 days are deleted: log in again when you get an `AuthenticationError`.

The user needs the "API use" permission, and the installation's plan must include the API; otherwise the API answers `403` (`is_plan_restriction()` tells the plan case apart).

**OAuth.** Pass the access token the same way. Reads need the `mopux:read` scope and writes `mopux:write`. Tokens created for the MCP connector are rejected by the REST API.

**Several installations.** Create one client per installation, or derive one with another token with `mopux.with_token(token)` (it shares the HTTP connections).

## Resources

| Attribute | Covers |
| --- | --- |
| `mopux.auth` | `login`, `logout`, `user`, `tokens.list()` / `tokens.delete()` |
| `mopux.projects` | `list`, `iter`, `create`, `show`, `update`, `delete`, `board`, `activity`, `summary`, members |
| `mopux.task_groups` | `create` (optionally with up to 4 tasks), `reorder`, `rename`, `archive`, `move`, `copy`, `create_project`, `focus`, `status_summary` |
| `mopux.tasks` | `create`, `update`, `update_batch`, `my`, `show`, `delete`, single-field updates, `move`, `send_touch`, focus list, documents |
| `mopux.comments` | `list`, `iter`, `create` (with mentions and files), `update`, `delete`, `reply` |
| `mopux.notifications` | `list`, `iter`, `mark_read`, `mark_unread`, `mark_all_read`, `unread_count`, `delete` |
| `mopux.touches` | `list`, `reply` |
| `mopux.team` / `mopux.team_invitations` | installation users, invitations |

### Updating tasks

`update()` changes only the arguments you pass, atomically. `None` clears description, dates and hours; leaving an argument out keeps the value. Assignees are an explicit mutation:

```python
mopux.tasks.update(
    101,
    date_end=None,
    hours_inverted="1:15",
    assignees={"operation": "add", "user_ids": [8]},  # or "remove" / "replace"
)
```

Hours are `HH:MM` (or minutes); the API returns them as `HH:MM:SS`. Status `-1` (delayed) is read only.

### Comments and documents

```python
from mopux import Upload

mopux.comments.create(101, "Draft attached @Ada#5", files=[Upload.from_path("draft.pdf")])
attachment = mopux.tasks.upload_file(101, Upload.from_bytes("hello", "notes.txt"))
```

Download URLs expire after 15 minutes.

### Pagination

Listings return a `Page` (`items`, `current_page`, `last_page`, `per_page`, `total`, `has_more()`, `next_page()`); the `iter…()` methods walk every page lazily. `tasks.my()` is not paginated. Prefer the aggregated endpoints (`projects.board()`, `projects.summary()`, `tasks.my()`) to fetching objects one by one.

## Errors

Every error extends `MopuxError`.

| Error | When |
| --- | --- |
| `AuthenticationError` | 401: missing, invalid or revoked token |
| `AuthorizationError` | 403: no permission, missing OAuth scope, plan restriction or blocked billing |
| `NotFoundError` | 404 |
| `ValidationError` | 422: `errors` holds the messages per field |
| `RateLimitError` | 429 after the retries; `retry_after` holds the seconds to wait |
| `ClientError` | other 4xx |
| `ServerError` | 5xx on a read |
| `UncertainWriteError` | 5xx on a write: the change **may have been applied** |
| `MopuxConnectionError` | network failure; `is_write_outcome_uncertain` is true for writes |
| `InvalidInputError` | rejected before sending (also a `ValueError`) |
| `MalformedResponseError` | unexpected response shape |

Every `ApiError` gives `status`, `body`, `api_message` and `code`, the stable machine-readable `data.code`. Branch on the code, never on the message: `is_plan_restriction()` (with `plan_feature`) and `is_billing_blocked()`.

```python
from mopux import UncertainWriteError, ValidationError

try:
    mopux.tasks.create(12, 7, "")
except ValidationError as error:
    print(error.errors)
except UncertainWriteError:
    ...  # Do not create the task again blindly: check whether it exists first.
```

## Retries

Enabled by default (2 retries, exponential backoff with jitter): `429` is retried for every method honouring `Retry-After` up to 60 seconds; network errors and `5xx` are retried for reads only; writes are **never** retried after a network error or a `5xx`.

```python
from mopux import Mopux, RetryPolicy

Mopux(url, token, retry=RetryPolicy(max_retries=4))
Mopux(url, token, retry=RetryPolicy.none())
```

Other options: `timeout` (seconds, default 30), `user_agent` (appended to the SDK one), `headers` and `http_client` (your own `httpx.Client` / `httpx.AsyncClient`, e.g. for proxies or custom certificates).

## Recibir webhooks

Configura `MOPUX_WEBHOOK_SECRET` con el secreto del endpoint. Pasa a
`parse_webhook_event` los bytes originales del POST y sus cabeceras. El SDK
comprueba la firma y aplica una tolerancia de 300 segundos antes de leer el JSON.

### FastAPI

```python
import os

from fastapi import FastAPI, Request, Response
from mopux import InvalidWebhookPayloadError, InvalidWebhookSignatureError, parse_webhook_event

app = FastAPI()
secret = os.environ["MOPUX_WEBHOOK_SECRET"]


@app.post("/webhooks/mopux")
async def receive(request: Request) -> Response:
    try:
        event = parse_webhook_event(await request.body(), request.headers, secret)
    except InvalidWebhookSignatureError:
        return Response(status_code=401)
    except InvalidWebhookPayloadError:
        return Response(status_code=400)

    # Registra event.delivery_id y encola el trabajo una sola vez por entrega.
    return Response(status_code=204)
```

### Flask

```python
import os

from flask import Flask, request
from mopux import InvalidWebhookPayloadError, InvalidWebhookSignatureError, parse_webhook_event

app = Flask(__name__)
secret = os.environ["MOPUX_WEBHOOK_SECRET"]


@app.post("/webhooks/mopux")
def receive():
    try:
        event = parse_webhook_event(request.get_data(), request.headers, secret)
    except InvalidWebhookSignatureError:
        return "", 401
    except InvalidWebhookPayloadError:
        return "", 400

    # Registra event.delivery_id y encola el trabajo una sola vez por entrega.
    return "", 204
```

`event.event` es un `WebhookEventType` para eventos conocidos y una cadena para
eventos nuevos. `event.task` devuelve un `TaskDetail` cuando hay una tarea completa.
Para una tarea borrada devuelve `None` y el objeto reducido queda en
`event.data["task"]`. También puedes consultar `event.previous_status`,
`event.changes`, `event.assigned_user_ids`, `event.previous_project_id` y
`event.previous_group_id`.

Usa `event.delivery_id` como clave de idempotencia. Los reintentos mantienen
ese identificador. Un reenvío manual genera un identificador de entrega nuevo
y conserva `event.id`. Responde con un 2xx tras registrar la entrega y encolar
el trabajo. Si solo necesitas validar la firma, llama a
`verify_webhook_signature(raw_body, signature_header, secret)`.

## Testing

```python
from mopux import Mopux
from mopux.testing import MockApi

api = MockApi().push(MockApi.json([{"id": 1, "title": "Review"}]), MockApi.plan_restricted())
mopux = Mopux("https://acme.test", "test", http_client=api.client())

mopux.tasks.my()
api.assert_sent("GET", "tasks/my")
```

Use `api.async_client()` with `AsyncMopux`. Helpers: `MockApi.json()`, `error()`, `validation()`, `plan_restricted()`, `network_error()`, `always()` and `assert_nothing_sent()`.

## Development

```bash
uv sync
uv run pytest                      # unit and contract tests (71/71 operations, sync and async)
uv run mypy src && uv run ruff check src tests scripts
uv run python scripts/generate.py  # regenerate the models from spec/openapi.yaml
uv run python scripts/unasync.py   # regenerate src/mopux/_sync from src/mopux/_async
```

Only edit `src/mopux/_async`; the sync client is generated and CI fails if it is out of date. Integration tests run against a real installation: `MOPUX_INTEGRATION_URL=… MOPUX_INTEGRATION_TOKEN=… uv run pytest -m integration`.

## License

MIT. See [LICENSE](LICENSE).
