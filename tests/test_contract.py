"""Contract between the SDK and spec/openapi.yaml (copy of mopux-com/docs/api/openapi-v1-public.yaml).

Every operation of the spec maps to an SDK call; each call runs against MockApi, in the sync and the
async client, and must hit the documented method and path.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from mopux import AsyncMopux, Mopux, Upload
from mopux.testing import MockApi

UUID = "9b2f6a3e-1c1d-4e8f-9f0a-6f1d2c3b4a5e"

OPERATIONS: dict[str, Callable[[Any], Any]] = {
    "POST /api/v1/auth/login": lambda m: m.auth.login("ada@acme.test", "secret"),
    "POST /api/v1/auth/logout": lambda m: m.auth.logout(),
    "GET /api/v1/auth/user": lambda m: m.auth.user(),
    "GET /api/v1/auth/tokens": lambda m: m.auth.tokens.list(),
    "DELETE /api/v1/auth/tokens/{tokenId}": lambda m: m.auth.tokens.delete(9),
    "GET /api/v1/projects": lambda m: m.projects.list(),
    "POST /api/v1/projects": lambda m: m.projects.create("Web"),
    "GET /api/v1/projects/{projectId}": lambda m: m.projects.show(12),
    "PATCH /api/v1/projects/{projectId}": lambda m: m.projects.update(12, status=1),
    "DELETE /api/v1/projects/{projectId}": lambda m: m.projects.delete(12, "web"),
    "GET /api/v1/projects/{projectId}/activity": lambda m: m.projects.activity(12),
    "GET /api/v1/projects/{projectId}/members": lambda m: m.projects.members(12),
    "POST /api/v1/projects/{projectId}/members": lambda m: m.projects.add_member(12, 5),
    "DELETE /api/v1/projects/{projectId}/members/{userId}": lambda m: m.projects.remove_member(12, 5),
    "GET /api/v1/projects/{projectId}/summary": lambda m: m.projects.summary(12),
    "GET /api/v1/projects/{projectId}/board": lambda m: m.projects.board(12),
    "POST /api/v1/projects/{projectId}/task-groups": lambda m: m.task_groups.create(12, "Backlog"),
    "PATCH /api/v1/projects/{projectId}/task-groups/reorder": lambda m: m.task_groups.reorder(12, [8, 7]),
    "PATCH /api/v1/projects/{projectId}/task-groups/{taskGroupId}/tasks/reorder": lambda m: m.task_groups.reorder_tasks(
        12, 7, [101]
    ),
    "PATCH /api/v1/projects/{projectId}/task-groups/{taskGroupId}/title": lambda m: m.task_groups.rename(12, 7, "R"),
    "PATCH /api/v1/projects/{projectId}/task-groups/{taskGroupId}/archive": lambda m: m.task_groups.archive(12, 7),
    "PATCH /api/v1/projects/{projectId}/task-groups/{taskGroupId}/unarchive": lambda m: m.task_groups.unarchive(12, 7),
    "PATCH /api/v1/projects/{projectId}/task-groups/{taskGroupId}/move": lambda m: m.task_groups.move(12, 7, 13),
    "PATCH /api/v1/projects/{projectId}/task-groups/{taskGroupId}/copy": lambda m: m.task_groups.copy(12, 7, 13, "C"),
    "POST /api/v1/projects/{projectId}/task-groups/{taskGroupId}/create-project": lambda m: (
        m.task_groups.create_project(12, 7, "Spin-off")
    ),
    "DELETE /api/v1/projects/{projectId}/task-groups/{taskGroupId}": lambda m: m.task_groups.delete(12, 7),
    "GET /api/v1/projects/{projectId}/task-groups/{taskGroupId}/focus": lambda m: m.task_groups.focus(12, 7),
    "GET /api/v1/projects/{projectId}/task-groups/{taskGroupId}/status-summary": lambda m: m.task_groups.status_summary(
        12, 7
    ),
    "POST /api/v1/tasks": lambda m: m.tasks.create(12, 7, "x"),
    "PATCH /api/v1/tasks/batch": lambda m: m.tasks.update_batch([{"id": 101, "changes": {"task_group_id": 8}}]),
    "GET /api/v1/tasks/my": lambda m: m.tasks.my(),
    "GET /api/v1/tasks/markdown-help": lambda m: m.tasks.markdown_help(),
    "GET /api/v1/tasks/focus": lambda m: m.tasks.focus(),
    "POST /api/v1/tasks/{taskId}/focus": lambda m: m.tasks.pin_focus(101),
    "DELETE /api/v1/tasks/{taskId}/focus": lambda m: m.tasks.unpin_focus(101),
    "GET /api/v1/tasks/{taskId}/move-options": lambda m: m.tasks.move_options(101),
    "GET /api/v1/tasks/{taskId}/attachments": lambda m: m.tasks.attachments(101),
    "POST /api/v1/tasks/{taskId}/files": lambda m: m.tasks.upload_file(101, Upload.from_bytes("x", "a.txt")),
    "DELETE /api/v1/tasks/{taskId}/files/{mediaId}": lambda m: m.tasks.delete_file(101, 77),
    "GET /api/v1/tasks/{taskId}": lambda m: m.tasks.show(101),
    "PATCH /api/v1/tasks/{taskId}": lambda m: m.tasks.update(101, title="x"),
    "DELETE /api/v1/tasks/{taskId}": lambda m: m.tasks.delete(101),
    "PATCH /api/v1/tasks/{taskId}/status": lambda m: m.tasks.update_status(101, 3),
    "PATCH /api/v1/tasks/{taskId}/priority": lambda m: m.tasks.update_priority(101, 2),
    "PATCH /api/v1/tasks/{taskId}/assign": lambda m: m.tasks.assign(101, 5),
    "PATCH /api/v1/tasks/{taskId}/move": lambda m: m.tasks.move(101, 13, 20),
    "PATCH /api/v1/tasks/{taskId}/title": lambda m: m.tasks.update_title(101, "x"),
    "PATCH /api/v1/tasks/{taskId}/description": lambda m: m.tasks.update_description(101, "x"),
    "PATCH /api/v1/tasks/{taskId}/start": lambda m: m.tasks.update_start(101, "2026-11-20"),
    "PATCH /api/v1/tasks/{taskId}/end": lambda m: m.tasks.update_end(101, "2026-11-30"),
    "PATCH /api/v1/tasks/{taskId}/hours": lambda m: m.tasks.update_hours(101, expected="1:00"),
    "POST /api/v1/tasks/{taskId}/touches": lambda m: m.tasks.send_touch(101, 5),
    "GET /api/v1/tasks/{taskId}/comments": lambda m: m.comments.list(101),
    "POST /api/v1/tasks/{taskId}/comments": lambda m: m.comments.create(101, "Hola"),
    "PATCH /api/v1/comments/{commentId}": lambda m: m.comments.update(55, "x"),
    "DELETE /api/v1/comments/{commentId}": lambda m: m.comments.delete(55),
    "POST /api/v1/comments/{commentId}/reply": lambda m: m.comments.reply(55, "x"),
    "GET /api/v1/notifications": lambda m: m.notifications.list(),
    "PATCH /api/v1/notifications/{notificationId}/read": lambda m: m.notifications.mark_read(UUID),
    "PATCH /api/v1/notifications/{notificationId}/unread": lambda m: m.notifications.mark_unread(UUID),
    "PATCH /api/v1/notifications/read-all": lambda m: m.notifications.mark_all_read(),
    "GET /api/v1/notifications/badge": lambda m: m.notifications.unread_count(),
    "DELETE /api/v1/notifications": lambda m: m.notifications.delete_all(),
    "DELETE /api/v1/notifications/{notificationId}": lambda m: m.notifications.delete(UUID),
    "GET /api/v1/touches": lambda m: m.touches.list(),
    "POST /api/v1/touches/{touchId}/reply": lambda m: m.touches.reply(4, "Hecho"),
    "GET /api/v1/team": lambda m: m.team.list(),
    "GET /api/v1/team/invitations": lambda m: m.team_invitations.list(),
    "POST /api/v1/team/invitations": lambda m: m.team_invitations.create("new@acme.test", 2),
    "POST /api/v1/team/invitations/{invitationId}/resend": lambda m: m.team_invitations.resend(2),
    "DELETE /api/v1/team/invitations/{invitationId}": lambda m: m.team_invitations.delete(2),
}


def spec_operations() -> list[str]:
    spec = yaml.safe_load((Path(__file__).parent.parent / "spec/openapi.yaml").read_text())
    return sorted(
        f"{method.upper()} {path}"
        for path, methods in spec["paths"].items()
        for method in methods
        if method in ("get", "post", "put", "patch", "delete")
    )


def matches(template: str, path: str) -> bool:
    pattern = re.sub(r"\{[^}]+\}", "[^/]+", template.removeprefix("/api/v1/"))
    return re.fullmatch(pattern, path) is not None


def test_every_operation_of_the_spec_is_mapped() -> None:
    assert sorted(OPERATIONS) == spec_operations()
    assert len(OPERATIONS) == 71


@pytest.mark.parametrize("operation", sorted(OPERATIONS))
def test_sync_call_hits_the_documented_endpoint(operation: str) -> None:
    method, template = operation.split(" ")
    api = MockApi().always(MockApi.json({}))
    OPERATIONS[operation](Mopux("https://acme.test", "t", http_client=api.client()))
    assert [(r.method, matches(template, r.path)) for r in api.requests] == [(method, True)]


@pytest.mark.parametrize("operation", sorted(OPERATIONS))
async def test_async_call_hits_the_documented_endpoint(operation: str) -> None:
    method, template = operation.split(" ")
    api = MockApi().always(MockApi.json({}))
    async with AsyncMopux("https://acme.test", "t", http_client=api.async_client()) as mopux:
        await OPERATIONS[operation](mopux)
    assert [(r.method, matches(template, r.path)) for r in api.requests] == [(method, True)]
