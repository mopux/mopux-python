"""Runs the whole API flow against a real installation (local or staging, never production).

    MOPUX_INTEGRATION_URL=https://acme.mopux.test MOPUX_INTEGRATION_TOKEN=… uv run pytest -m integration

It creates a temporary project and deletes it at the end. MOPUX_INTEGRATION_UPLOADS=1 also exercises
file uploads. For a local certificate authority set SSL_CERT_FILE to the system bundle.
"""

from __future__ import annotations

import contextlib
import os
from datetime import UTC, datetime

import pytest

from mopux import Mopux, NotFoundError, Upload

pytestmark = pytest.mark.integration

URL = os.environ.get("MOPUX_INTEGRATION_URL")
TOKEN = os.environ.get("MOPUX_INTEGRATION_TOKEN")


@pytest.mark.skipif(not (URL and TOKEN), reason="MOPUX_INTEGRATION_URL and MOPUX_INTEGRATION_TOKEN are not set")
def test_whole_api_flow() -> None:
    with Mopux(URL or "", TOKEN, user_agent="mopux-python-integration-tests") as mopux:
        me = mopux.auth.user()
        assert me.id
        mopux.projects.list(per_page=5)
        mopux.tasks.my()
        mopux.tasks.focus()
        mopux.tasks.markdown_help()
        with contextlib.suppress(NotFoundError):  # auth/tokens arrived in API 1.2
            mopux.auth.tokens.list()
        mopux.notifications.list(per_page=5)
        mopux.notifications.unread_count()

        project = mopux.projects.create(
            f"mopux-python {datetime.now(UTC).isoformat()}", description="Created by the mopux-python integration tests"
        )
        assert project.id
        try:
            mopux.projects.update(project.id, description="Updated by mopux-python")
            assert any(member.id == me.id for member in mopux.projects.members(project.id))

            group = mopux.task_groups.create(project.id, "Backlog", [{"title": "First task"}, {"title": "Second task"}])
            assert group.id and len(group.tasks) == 2

            task = mopux.tasks.create(
                project.id, group.id, "Third task", hours_expected="1:30", assignees=[me.id], tags=["sdk"]
            )
            assert task.id and task.hours_expected == "01:30:00"
            task = mopux.tasks.update(
                task.id,
                date_start="2026-12-01",
                date_end="2026-12-15",
                assignees={"operation": "replace", "user_ids": [me.id]},
            )
            task = mopux.tasks.update_status(task.id or 0, 2)
            task = mopux.tasks.update_priority(task.id or 0, 9)
            task = mopux.tasks.update_title(task.id or 0, "Third task (renamed)")
            task = mopux.tasks.update_description(task.id or 0, None)
            task = mopux.tasks.update_hours(task.id or 0, expected="2:00")
            assert task.title == "Third task (renamed)"
            task_id = task.id or 0

            mopux.tasks.update_batch([{"id": group.tasks[0].id, "changes": {"priority": 2}}])
            board = mopux.projects.board(project.id)
            assert board.task_groups
            summary = mopux.task_groups.status_summary(project.id, group.id)
            assert summary.summary is not None
            mopux.task_groups.focus(project.id, group.id)
            mopux.projects.summary(project.id)
            mopux.projects.activity(project.id, per_page=10)
            mopux.task_groups.reorder_tasks(project.id, group.id, [task_id])
            assert mopux.task_groups.rename(project.id, group.id, "Backlog (renamed)").title == "Backlog (renamed)"

            comment = mopux.comments.create(task_id, "Hello from mopux-python", mentions=[me.id])
            reply = mopux.comments.reply(comment.id or 0, "A reply")
            mopux.comments.update(comment.id or 0, "Hello from mopux-python (edited)")
            assert len(mopux.comments.list(task_id)) >= 2
            if os.environ.get("MOPUX_INTEGRATION_UPLOADS") == "1":
                mopux.comments.create(task_id, "With a file", files=[Upload.from_bytes("a,b\n1,2\n", "sdk-test.csv")])
                attachment = mopux.tasks.upload_file(task_id, Upload.from_bytes("plain text", "sdk-direct.txt"))
                assert len(mopux.tasks.attachments(task_id)) > 0
                mopux.tasks.delete_file(task_id, attachment.id or 0)
            mopux.comments.delete(reply.id or 0)

            mopux.tasks.move_options(task_id)
            assert mopux.task_groups.archive(project.id, group.id).status == 1
            assert mopux.task_groups.unarchive(project.id, group.id).status == 0
            mopux.tasks.delete(task_id)
            with pytest.raises(NotFoundError):
                mopux.tasks.show(task_id)
        finally:
            slug = mopux.projects.show(project.id).slug
            if slug:
                mopux.projects.delete(project.id, slug)
