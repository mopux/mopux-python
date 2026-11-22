# Generated from src/mopux/_async by scripts/unasync.py. Do not edit.
from __future__ import annotations

import builtins
import re
from collections.abc import Iterator, Sequence
from datetime import date as Date
from typing import Any, Literal

from .. import _validate as v
from .._base import UNSET, Unset, compact, parse, parse_list, validator
from ..errors import InvalidInputError
from ..models import (
    ApiToken,
    Attachment,
    AuthenticatedUser,
    AuthTokenData,
    Comment,
    FocusList,
    GroupStatusSummary,
    MarkdownHelp,
    MovedTask,
    MoveOptions,
    Notification,
    Position,
    ProjectActivity,
    ProjectBoard,
    ProjectDetail,
    ProjectMember,
    ProjectStatistics,
    ProjectSummary,
    TaskDetail,
    TaskGroup,
    TaskGroupFocus,
    TaskGroupWithTasks,
    TaskSummary,
    TeamInvitation,
    TeamMember,
    Touch,
)
from ..page import Page
from ..upload import Upload
from .connector import Connector
from .pagination import iterate_pages

TaskStatusValue = Literal[0, 1, 2, 3]
TaskPriorityValue = Literal[0, 1, 2, 9]
ProjectStatusValue = Literal[-1, 0, 1, 2]
DateInput = str | Date
HoursInput = str | int

_UUID = re.compile(r"^[0-9a-f-]{36}$", re.IGNORECASE)


def _date_or_none(value: DateInput | None, field: str) -> str | None:
    return None if value is None else v.date(value, field)


class _Resource:
    def __init__(self, connector: Connector) -> None:
        self._c = connector


class AuthTokens(_Resource):
    def list(self) -> builtins.list[ApiToken]:
        """API tokens of the authenticated user (never their secrets)."""
        return parse_list(ApiToken, self._c.get("auth/tokens"))

    def delete(self, token_id: int) -> None:
        """Revokes an API token of the user. Revoking the current one logs out."""
        self._c.delete(f"auth/tokens/{v.id_(token_id, 'token_id')}")


class Auth(_Resource):
    def __init__(self, connector: Connector) -> None:
        super().__init__(connector)
        self.tokens = AuthTokens(connector)

    def login(self, email: str, password: str, token_name: str | None = None) -> AuthTokenData:
        """Exchanges email and password for a new personal token. Each login creates a token."""
        body: dict[str, Any] = {"email": v.text(email, "email"), "password": password}
        if token_name is not None:
            body["token_name"] = v.text(token_name, "token_name", 255)
        return parse(AuthTokenData, self._c.post("auth/login", body))

    def logout(self) -> None:
        """Revokes the token used for the request."""
        self._c.post("auth/logout")

    def user(self) -> AuthenticatedUser:
        data = self._c.get("auth/user")
        return parse(AuthenticatedUser, data.get("user") if isinstance(data, dict) else None)


class Projects(_Resource):
    def list(self, *, search: str | None = None, page: int = 1, per_page: int = 20) -> Page[ProjectSummary]:
        """Projects visible to the user, ordered by title."""
        page, per_page = v.page(page), v.per_page(per_page)
        data = self._c.get("projects", {"q": search, "page": page, "per_page": per_page})
        return Page.parse(data, validator(ProjectSummary), page, per_page)

    def iter(self, *, search: str | None = None, per_page: int = 100) -> Iterator[ProjectSummary]:
        """Every project, page after page."""
        return iterate_pages(lambda page: self.list(search=search, page=page, per_page=per_page))

    def create(
        self,
        title: str,
        *,
        description: str | Unset | None = UNSET,
        date_starts: DateInput | Unset | None = UNSET,
        date_ends: DateInput | Unset | None = UNSET,
    ) -> ProjectDetail:
        body = compact(
            title=v.title(title),
            description=description,
            date_starts=date_starts if isinstance(date_starts, Unset) else _date_or_none(date_starts, "date_starts"),
            date_ends=date_ends if isinstance(date_ends, Unset) else _date_or_none(date_ends, "date_ends"),
        )
        return parse(ProjectDetail, self._c.post("projects", body))

    def show(self, project_id: int) -> ProjectDetail:
        return parse(ProjectDetail, self._c.get(_project(project_id)))

    def update(
        self,
        project_id: int,
        *,
        title: str | Unset = UNSET,
        description: str | Unset | None = UNSET,
        date_starts: DateInput | Unset | None = UNSET,
        date_ends: DateInput | Unset | None = UNSET,
        status: ProjectStatusValue | Unset = UNSET,
        notify_comments: bool | Unset = UNSET,
        notify_tasks: bool | Unset = UNSET,
        notify_documents: bool | Unset = UNSET,
    ) -> ProjectDetail:
        """Only the given fields change; None clears description and dates."""
        body = compact(
            title=title if isinstance(title, Unset) else v.title(title),
            description=description,
            date_starts=date_starts if isinstance(date_starts, Unset) else _date_or_none(date_starts, "date_starts"),
            date_ends=date_ends if isinstance(date_ends, Unset) else _date_or_none(date_ends, "date_ends"),
            status=status,
            notify_comments=notify_comments,
            notify_tasks=notify_tasks,
            notify_documents=notify_documents,
        )
        if not body:
            raise InvalidInputError("changes", "provide at least one field to update.")
        return parse(ProjectDetail, self._c.patch(_project(project_id), body))

    def delete(self, project_id: int, confirm_slug: str) -> None:
        """Deletes the project. ``confirm_slug`` must be the project slug, as a safeguard."""
        self._c.delete(_project(project_id), json={"confirm": v.text(confirm_slug, "confirm_slug")})

    def board(
        self,
        project_id: int,
        *,
        search: str | None = None,
        include_archived: bool = False,
        users: Sequence[int] = (),
        statuses: Sequence[int] = (),
        priorities: Sequence[int] = (),
    ) -> ProjectBoard:
        """The whole board in one request: groups in order with their open tasks, and the members."""
        params: dict[str, Any] = {}
        if users:
            params["users"] = v.ids(users, "users")
        if statuses:
            params["status"] = list(statuses)
        if priorities:
            params["priority"] = list(priorities)
        data = self._c.get(
            _project(project_id, "board"),
            {"archived": include_archived, "search": search, "params": params or None},
        )
        return parse(ProjectBoard, data)

    def activity(
        self,
        project_id: int,
        *,
        filter: str | None = None,
        type: str | None = None,
        user_id: int | None = None,
        date_from: DateInput | None = None,
        date_to: DateInput | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> Page[ProjectActivity]:
        """Activity log, newest first."""
        start = _date_or_none(date_from, "date_from")
        end = _date_or_none(date_to, "date_to")
        if start is not None and end is not None and end < start:
            raise InvalidInputError("date_to", "cannot be before date_from.")
        page, per_page = v.page(page), v.per_page(per_page)
        data = self._c.get(
            _project(project_id, "activity"),
            {
                "filter": filter,
                "type": type,
                "user_id": None if user_id is None else v.id_(user_id, "user_id"),
                "from": start,
                "to": end,
                "page": page,
                "per_page": per_page,
            },
        )
        return Page.parse(data, validator(ProjectActivity), page, per_page)

    def iter_activity(self, project_id: int, *, per_page: int = 100, **filters: Any) -> Iterator[ProjectActivity]:
        return iterate_pages(lambda page: self.activity(project_id, page=page, per_page=per_page, **filters))

    def summary(self, project_id: int) -> ProjectStatistics:
        """Progress per group and workload per member."""
        return parse(ProjectStatistics, self._c.get(_project(project_id, "summary")))

    def members(self, project_id: int) -> builtins.list[ProjectMember]:
        return _members(self._c.get(_project(project_id, "members")))

    def add_member(self, project_id: int, user_id: int) -> builtins.list[ProjectMember]:
        """Adds an installation user to the project and returns the members."""
        data = self._c.post(_project(project_id, "members"), {"user_id": v.id_(user_id, "user_id")})
        return _members(data)

    def remove_member(self, project_id: int, user_id: int) -> builtins.list[ProjectMember]:
        return _members(self._c.delete(_project(project_id, f"members/{v.id_(user_id, 'user_id')}")))


class TaskGroups(_Resource):
    def create(self, project_id: int, title: str, tasks: Sequence[dict[str, Any]] = ()) -> TaskGroupWithTasks:
        """Creates a group, optionally with up to 4 tasks in one atomic operation."""
        if len(tasks) > 4:
            raise InvalidInputError("tasks", "at most 4 tasks can be created with a group.")
        body: dict[str, Any] = {"title": v.title(title)}
        if tasks:
            body["tasks"] = [{**task, "title": v.title(str(task.get("title", "")))} for task in tasks]
        data = self._c.post(_groups(project_id), body)
        if isinstance(data, dict) and isinstance(data.get("group"), dict):
            data = {**data["group"], "tasks": data.get("tasks") or []}
        return parse(TaskGroupWithTasks, data)

    def reorder(self, project_id: int, group_ids: Sequence[int]) -> builtins.list[Position]:
        """Sets the order of the project's groups: the first id goes first."""
        data = self._c.patch(_groups(project_id, "reorder"), {"groups": _order(group_ids, "group_ids")})
        return parse_list(Position, data.get("task_groups") if isinstance(data, dict) else None)

    def reorder_tasks(self, project_id: int, group_id: int, task_ids: Sequence[int]) -> builtins.list[Position]:
        """Sets the manual order of the tasks of a group: the first id goes first."""
        data = self._c.patch(
            _groups(project_id, f"{v.id_(group_id, 'group_id')}/tasks/reorder"), {"tasks": _order(task_ids, "task_ids")}
        )
        return parse_list(Position, data.get("tasks") if isinstance(data, dict) else None)

    def rename(self, project_id: int, group_id: int, title: str) -> TaskGroup:
        return self._patch(project_id, group_id, "title", {"title": v.title(title)})

    def archive(self, project_id: int, group_id: int) -> TaskGroup:
        return self._patch(project_id, group_id, "archive")

    def unarchive(self, project_id: int, group_id: int) -> TaskGroup:
        return self._patch(project_id, group_id, "unarchive")

    def move(self, project_id: int, group_id: int, to_project_id: int) -> TaskGroup:
        """Moves the group, with its tasks, to another project."""
        return self._patch(project_id, group_id, "move", {"project_id": v.id_(to_project_id, "to_project_id")})

    def copy(self, project_id: int, group_id: int, to_project_id: int, title: str) -> TaskGroup:
        """Copies the group, with its tasks, to a project (the same or another)."""
        body = {"project_id": v.id_(to_project_id, "to_project_id"), "title": v.title(title)}
        return self._patch(project_id, group_id, "copy", body)

    def create_project(
        self, project_id: int, group_id: int, title: str, description: str | Unset | None = UNSET
    ) -> ProjectDetail:
        """Creates a new project from the group and its tasks."""
        body = compact(title=v.title(title), description=description)
        data = self._c.post(_groups(project_id, f"{v.id_(group_id, 'group_id')}/create-project"), body)
        return parse(ProjectDetail, data)

    def delete(self, project_id: int, group_id: int) -> None:
        self._c.delete(_groups(project_id, str(v.id_(group_id, "group_id"))))

    def focus(self, project_id: int, group_id: int, search: str | None = None) -> TaskGroupFocus:
        """The group with its tasks ordered by status."""
        data = self._c.get(_groups(project_id, f"{v.id_(group_id, 'group_id')}/focus"), {"search": search})
        record: dict[str, Any] = data if isinstance(data, dict) else {}
        group: dict[str, Any] = record["group"] if isinstance(record.get("group"), dict) else {}
        return parse(TaskGroupFocus, {**group, "tasks": record.get("tasks") or []})

    def status_summary(self, project_id: int, group_id: int) -> GroupStatusSummary:
        """Number of tasks per status, including delayed ones."""
        data = self._c.get(_groups(project_id, f"{v.id_(group_id, 'group_id')}/status-summary"))
        return parse(GroupStatusSummary, data)

    def _patch(self, project_id: int, group_id: int, action: str, body: Any = None) -> TaskGroup:
        data = self._c.patch(_groups(project_id, f"{v.id_(group_id, 'group_id')}/{action}"), body)
        return parse(TaskGroup, data)


class Tasks(_Resource):
    def create(
        self,
        project_id: int,
        group_id: int,
        title: str,
        *,
        description: str | Unset | None = UNSET,
        status: TaskStatusValue | Unset = UNSET,
        priority: TaskPriorityValue | Unset = UNSET,
        date_start: DateInput | Unset | None = UNSET,
        date_end: DateInput | Unset | None = UNSET,
        hours_expected: HoursInput | Unset | None = UNSET,
        hours_inverted: HoursInput | Unset | None = UNSET,
        tags: Sequence[str] | Unset = UNSET,
        assignees: Sequence[int] | Unset = UNSET,
    ) -> TaskDetail:
        """Creates a task. A 5xx raises UncertainWriteError: check before creating it again."""
        body = compact(
            project_id=v.id_(project_id, "project_id"),
            group_id=v.id_(group_id, "group_id"),
            title=v.title(title),
            description=description,
            status=status,
            priority=priority,
            date_start=_maybe_date(date_start, "date_start"),
            date_end=_maybe_date(date_end, "date_end"),
            hours_expected=_maybe_hours(hours_expected, "hours_expected"),
            hours_inverted=_maybe_hours(hours_inverted, "hours_inverted"),
            tags=tags if isinstance(tags, Unset) else list(tags),
            assignees=assignees if isinstance(assignees, Unset) else v.ids(assignees, "assignees"),
        )
        return parse(TaskDetail, self._c.post("tasks", body))

    def update(
        self,
        task_id: int,
        *,
        title: str | Unset = UNSET,
        description: str | Unset | None = UNSET,
        status: TaskStatusValue | Unset = UNSET,
        priority: TaskPriorityValue | Unset = UNSET,
        date_start: DateInput | Unset | None = UNSET,
        date_end: DateInput | Unset | None = UNSET,
        hours_expected: HoursInput | Unset | None = UNSET,
        hours_inverted: HoursInput | Unset | None = UNSET,
        tags: Sequence[str] | Unset = UNSET,
        assignees: dict[str, Any] | Unset = UNSET,
    ) -> TaskDetail:
        """Updates only the given fields, atomically. None clears description, dates and hours.
        ``assignees`` is a mutation: ``{"operation": "add" | "remove" | "replace", "user_ids": [...]}``."""
        body = compact(
            title=title if isinstance(title, Unset) else v.title(title),
            description=description,
            status=status,
            priority=priority,
            date_start=_maybe_date(date_start, "date_start"),
            date_end=_maybe_date(date_end, "date_end"),
            hours_expected=_maybe_hours(hours_expected, "hours_expected"),
            hours_inverted=_maybe_hours(hours_inverted, "hours_inverted"),
            tags=tags if isinstance(tags, Unset) else list(tags),
            assignees=assignees,
        )
        if not body:
            raise InvalidInputError("changes", "provide at least one field to update.")
        return parse(TaskDetail, self._c.patch(_task(task_id), body))

    def update_batch(self, tasks: Sequence[dict[str, Any]]) -> builtins.list[TaskDetail]:
        """Updates up to 4 tasks atomically: ``[{"id": 101, "changes": {...}}, ...]``."""
        if not 1 <= len(tasks) <= 4:
            raise InvalidInputError("tasks", "provide between 1 and 4 tasks.")
        data = self._c.patch("tasks/batch", {"tasks": list(tasks)})
        return parse_list(TaskDetail, data.get("tasks") if isinstance(data, dict) else None)

    def my(self, *, search: str | None = None, project_ids: Sequence[int] = ()) -> builtins.list[TaskSummary]:
        """Tasks assigned to the user: open ones and those done in the last 15 days. Not paginated."""
        params = {"projects": v.ids(project_ids, "project_ids")} if project_ids else None
        return parse_list(TaskSummary, self._c.get("tasks/my", {"search": search, "params": params}))

    def show(self, task_id: int) -> TaskDetail:
        return parse(TaskDetail, self._c.get(_task(task_id)))

    def delete(self, task_id: int) -> None:
        self._c.delete(_task(task_id))

    def update_status(self, task_id: int, status: TaskStatusValue) -> TaskDetail:
        if status not in (0, 1, 2, 3):
            raise InvalidInputError("status", "must be 0, 1, 2 or 3 (delayed, -1, is read only).")
        return self._patch(task_id, "status", {"status": status})

    def update_priority(self, task_id: int, priority: TaskPriorityValue) -> TaskDetail:
        return self._patch(task_id, "priority", {"priority": priority})

    def assign(self, task_id: int, user_id: int | None) -> TaskDetail:
        """Legacy single assignment (None unassigns everybody). Prefer update(assignees=...)."""
        return self._patch(task_id, "assign", {"assignee_id": None if user_id is None else v.id_(user_id, "user_id")})

    def move(self, task_id: int, project_id: int, group_id: int) -> MovedTask:
        """Moves the task to a group of the same or another project."""
        body = {"project_id": v.id_(project_id, "project_id"), "group_id": v.id_(group_id, "group_id")}
        return parse(MovedTask, self._c.patch(_task(task_id, "move"), body))

    def update_title(self, task_id: int, title: str) -> TaskDetail:
        return self._patch(task_id, "title", {"title": v.title(title)})

    def update_description(self, task_id: int, description: str | None) -> TaskDetail:
        return self._patch(task_id, "description", {"description": description})

    def update_start(self, task_id: int, date: DateInput | None) -> TaskDetail:
        return self._patch(task_id, "start", {"date_start": _date_or_none(date, "date_start")})

    def update_end(self, task_id: int, date: DateInput | None) -> TaskDetail:
        return self._patch(task_id, "end", {"date_end": _date_or_none(date, "date_end")})

    def update_hours(
        self, task_id: int, *, expected: HoursInput | Unset | None = UNSET, inverted: HoursInput | Unset | None = UNSET
    ) -> TaskDetail:
        """Expected and/or worked hours (``HH:MM`` or minutes). Omitted values are kept; None clears."""
        body = compact(
            hours_expected=_maybe_hours(expected, "hours_expected"),
            hours_inverted=_maybe_hours(inverted, "hours_inverted"),
        )
        if not body:
            raise InvalidInputError("hours", "provide expected or inverted hours.")
        return self._patch(task_id, "hours", body)

    def send_touch(self, task_id: int, recipient_id: int, message: str | Unset | None = UNSET) -> Touch:
        """Sends a touch (a nudge about this task) to a project member."""
        body = compact(recipient_id=v.id_(recipient_id, "recipient_id"), message=message)
        return parse(Touch, self._c.post(_task(task_id, "touches"), body))

    def focus(self) -> FocusList:
        """The user's personal focus list."""
        return parse(FocusList, self._c.get("tasks/focus"))

    def pin_focus(self, task_id: int) -> FocusList:
        return parse(FocusList, self._c.post(_task(task_id, "focus")))

    def unpin_focus(self, task_id: int) -> FocusList:
        return parse(FocusList, self._c.delete(_task(task_id, "focus")))

    def move_options(self, task_id: int) -> MoveOptions:
        """Projects and groups the task can be moved to."""
        return parse(MoveOptions, self._c.get(_task(task_id, "move-options")))

    def attachments(self, task_id: int, *, page: int = 1, per_page: int = 20) -> Page[Attachment]:
        """Documents of the task and its comments. Download URLs expire after 15 minutes."""
        page, per_page = v.page(page), v.per_page(per_page)
        data = self._c.get(_task(task_id, "attachments"), {"page": page, "per_page": per_page})
        return Page.parse_fields(data, "attachments", validator(Attachment), per_page)

    def iter_attachments(self, task_id: int, *, per_page: int = 100) -> Iterator[Attachment]:
        return iterate_pages(lambda page: self.attachments(task_id, page=page, per_page=per_page))

    def upload_file(self, task_id: int, file: Upload) -> Attachment:
        """Uploads a document to the task (multipart)."""
        data = self._c.request("POST", _task(task_id, "files"), files=[("file", file.as_httpx())])
        return parse(Attachment, data)

    def delete_file(self, task_id: int, media_id: int) -> None:
        """Deletes a document the user uploaded to the task."""
        self._c.delete(_task(task_id, f"files/{v.id_(media_id, 'media_id')}"))

    def markdown_help(self) -> MarkdownHelp:
        """Markdown supported in descriptions and comments."""
        return parse(MarkdownHelp, self._c.get("tasks/markdown-help"))

    def _patch(self, task_id: int, action: str, body: Any) -> TaskDetail:
        return parse(TaskDetail, self._c.patch(_task(task_id, action), body))


class Comments(_Resource):
    def list(self, task_id: int, *, page: int = 1, per_page: int = 20) -> Page[Comment]:
        """Comments of a task, newest first."""
        page, per_page = v.page(page), v.per_page(per_page)
        data = self._c.get(_task(task_id, "comments"), {"page": page, "per_page": per_page})
        return Page.parse(data, validator(Comment), page, per_page)

    def iter(self, task_id: int, *, per_page: int = 100) -> Iterator[Comment]:
        return iterate_pages(lambda page: self.list(task_id, page=page, per_page=per_page))

    def create(
        self,
        task_id: int,
        comment: str | None = None,
        *,
        mentions: Sequence[int] = (),
        media_ids: Sequence[int] = (),
        files: Sequence[Upload] = (),
    ) -> Comment:
        """Publishes a comment (Markdown). With files the request is multipart and the files go to the task."""
        mention_ids = v.ids(mentions, "mentions")
        medias = v.ids(media_ids, "media_ids")
        if (comment is None or not comment.strip()) and not mention_ids and not medias and not files:
            raise InvalidInputError("comment", "a comment, files, documents or mentions are required.")
        path = _task(task_id, "comments")
        if not files:
            body = compact(
                comment=UNSET if comment is None else comment,
                mentions=mention_ids or UNSET,
                media_ids=medias or UNSET,
            )
            return parse(Comment, self._c.post(path, body))
        form: dict[str, Any] = {}
        if comment is not None:
            form["comment"] = comment
        if mention_ids:
            form["mentions[]"] = [str(item) for item in mention_ids]
        if medias:
            form["media_ids[]"] = [str(item) for item in medias]
        data = self._c.request("POST", path, data=form, files=[("files[]", file.as_httpx()) for file in files])
        return parse(Comment, data)

    def update(self, comment_id: int, comment: str) -> Comment:
        """Edits the text of a comment of the user."""
        return parse(Comment, self._c.patch(_comment(comment_id), {"comment": v.text(comment, "comment")}))

    def delete(self, comment_id: int, *, keep_files: bool | None = None) -> None:
        """Deletes a comment of the user. Its files stay in the task unless ``keep_files=False``."""
        self._c.delete(_comment(comment_id), {"keep_files": keep_files})

    def reply(self, comment_id: int, comment: str) -> Comment:
        data = self._c.post(_comment(comment_id, "reply"), {"comment": v.text(comment, "comment")})
        return parse(Comment, data)


class Notifications(_Resource):
    def list(
        self, *, filter: Literal["all", "read", "unread"] | None = None, page: int = 1, per_page: int = 25
    ) -> Page[Notification]:
        """Notifications of the user, newest first."""
        page, per_page = v.page(page), v.per_page(per_page)
        data = self._c.get("notifications", {"filter": filter, "page": page, "per_page": per_page})
        return Page.parse(data, validator(Notification), page, per_page)

    def iter(
        self, *, filter: Literal["all", "read", "unread"] | None = None, per_page: int = 100
    ) -> Iterator[Notification]:
        return iterate_pages(lambda page: self.list(filter=filter, page=page, per_page=per_page))

    def mark_read(self, notification_id: str) -> Notification:
        return parse(Notification, self._c.patch(_notification(notification_id, "read")))

    def mark_unread(self, notification_id: str) -> Notification:
        return parse(Notification, self._c.patch(_notification(notification_id, "unread")))

    def mark_all_read(self) -> int:
        """Marks everything as read and returns the unread count (0)."""
        return _count(self._c.patch("notifications/read-all"), "unread_count")

    def unread_count(self) -> int:
        return _count(self._c.get("notifications/badge"), "unread_count")

    def delete(self, notification_id: str) -> int:
        """Deletes a notification and returns the remaining unread count."""
        return _count(self._c.delete(_notification(notification_id)), "unread_count")

    def delete_all(self) -> int:
        """Deletes every notification of the user and returns how many were deleted."""
        return _count(self._c.delete("notifications"), "deleted")


class Touches(_Resource):
    def list(
        self, *, box: Literal["received", "sent"] = "received", status: Literal["pending", "answered"] | None = None
    ) -> builtins.list[Touch]:
        """Touches received (default) or sent by the user."""
        return parse_list(Touch, self._c.get("touches", {"box": box, "status": status}))

    def reply(self, touch_id: int, message: str) -> Touch:
        """Answers a received touch."""
        data = self._c.post(f"touches/{v.id_(touch_id, 'touch_id')}/reply", {"message": v.text(message, "message")})
        return parse(Touch, data)


class Team(_Resource):
    def list(
        self, *, search: str | None = None, role: str | None = None, page: int = 1, per_page: int = 25
    ) -> Page[TeamMember]:
        """Users of the installation. Requires permission to manage the team."""
        page, per_page = v.page(page), v.per_page(per_page)
        data = self._c.get("team", {"search": search, "role": role, "page": page, "per_page": per_page})
        return Page.parse_fields(data, "members", validator(TeamMember), per_page)

    def iter(self, *, search: str | None = None, role: str | None = None, per_page: int = 100) -> Iterator[TeamMember]:
        return iterate_pages(lambda page: self.list(search=search, role=role, page=page, per_page=per_page))


class TeamInvitations(_Resource):
    def list(
        self,
        *,
        search: str | None = None,
        status: Literal["all", "pending", "accepted"] = "all",
        page: int = 1,
        per_page: int = 20,
    ) -> Page[TeamInvitation]:
        page, per_page = v.page(page), v.per_page(per_page)
        data = self._c.get("team/invitations", {"q": search, "status": status, "page": page, "per_page": per_page})
        return Page.parse(data, validator(TeamInvitation), page, per_page)

    def iter(
        self, *, search: str | None = None, status: Literal["all", "pending", "accepted"] = "all", per_page: int = 100
    ) -> Iterator[TeamInvitation]:
        return iterate_pages(lambda page: self.list(search=search, status=status, page=page, per_page=per_page))

    def create(
        self, email: str, role_id: int, user_type: Literal["internal", "external"] | Unset = UNSET
    ) -> TeamInvitation:
        """Invites a user with a role. The user type follows the role; ``user_type`` must match it."""
        body = compact(email=v.text(email, "email"), rol=v.id_(role_id, "role_id"), user_type=user_type)
        return parse(TeamInvitation, self._c.post("team/invitations", body))

    def resend(self, invitation_id: int) -> TeamInvitation:
        data = self._c.post(f"team/invitations/{v.id_(invitation_id, 'invitation_id')}/resend")
        return parse(TeamInvitation, data)

    def delete(self, invitation_id: int) -> None:
        self._c.delete(f"team/invitations/{v.id_(invitation_id, 'invitation_id')}")


def _project(project_id: int, suffix: str = "") -> str:
    return f"projects/{v.id_(project_id, 'project_id')}" + (f"/{suffix}" if suffix else "")


def _groups(project_id: int, suffix: str = "") -> str:
    return _project(project_id, "task-groups" + (f"/{suffix}" if suffix else ""))


def _task(task_id: int, suffix: str = "") -> str:
    return f"tasks/{v.id_(task_id, 'task_id')}" + (f"/{suffix}" if suffix else "")


def _comment(comment_id: int, suffix: str = "") -> str:
    return f"comments/{v.id_(comment_id, 'comment_id')}" + (f"/{suffix}" if suffix else "")


def _notification(notification_id: str, suffix: str = "") -> str:
    if not _UUID.match(notification_id):
        raise InvalidInputError("notification_id", "expected a UUID.")
    return f"notifications/{notification_id}" + (f"/{suffix}" if suffix else "")


def _members(data: Any) -> builtins.list[ProjectMember]:
    return parse_list(ProjectMember, data.get("members") if isinstance(data, dict) else None)


def _count(data: Any, key: str) -> int:
    value = data.get(key) if isinstance(data, dict) else None
    return value if isinstance(value, int) else 0


def _order(ids: Sequence[int], field: str) -> builtins.list[dict[str, int]]:
    if not ids:
        raise InvalidInputError(field, "provide at least one id.")
    if len(set(ids)) != len(ids):
        raise InvalidInputError(field, "contains duplicates.")
    return [{"value": value, "order": index} for index, value in enumerate(v.ids(ids, field), start=1)]


def _maybe_date(value: DateInput | Unset | None, field: str) -> str | Unset | None:
    return value if isinstance(value, Unset) else _date_or_none(value, field)


def _maybe_hours(value: HoursInput | Unset | None, field: str) -> str | Unset | None:
    if isinstance(value, Unset) or value is None:
        return value
    return v.hours(value, field)
