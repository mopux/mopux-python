"""Models for responses the OpenAPI spec defines inline (not as components)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ._generated import Attachment, ProjectDetail, TaskBoard, TaskDetail, TaskGroup


class _Model(BaseModel):
    model_config = ConfigDict(extra="allow")


class Position(_Model):
    id: int | None = None
    title: str | None = None
    position: int | None = None
    group_position: int | None = None


class TaskGroupWithTasks(TaskGroup):
    """A group with the tasks created with it (empty when created without tasks)."""

    tasks: list[TaskDetail] = Field(default_factory=list)


class TaskGroupFocus(TaskGroup):
    tasks: list[TaskBoard] = Field(default_factory=list)


class StatusCounts(_Model):
    pending: int = 0
    doing: int = 0
    revision: int = 0
    done: int = 0
    delayed: int | None = None
    total: int | None = None


class GroupStatusSummary(_Model):
    group: TaskGroup | None = None
    summary: StatusCounts | None = None


class ProjectStatistics(_Model):
    """Progress per group and workload per member (``projects.summary``)."""

    project: dict[str, Any] | None = None
    total: int | None = None
    completed: int | None = None
    pending: int | None = None
    progress: int | None = None
    groups: list[dict[str, Any]] = []
    people: list[dict[str, Any]] = []


class MoveWarning(_Model):
    code: str | None = None
    user_id: int | None = None
    message: str | None = None


class MovedTask(TaskDetail):
    warnings: list[MoveWarning] = Field(default_factory=list)


class MoveOptions(_Model):
    current_project_id: int | None = None
    current_group_id: int | None = None
    projects: list[dict[str, Any]] = []


class MarkdownHelp(_Model):
    pass


class TeamMember(_Model):
    id: int | None = None
    name: str | None = None
    email: str | None = None
    avatar: str | None = None
    is_active: bool | None = None
    roles: list[str] = Field(default_factory=list)


__all__ = [
    "Attachment",
    "GroupStatusSummary",
    "MarkdownHelp",
    "MoveOptions",
    "MoveWarning",
    "MovedTask",
    "Position",
    "ProjectDetail",
    "ProjectStatistics",
    "StatusCounts",
    "TaskGroupFocus",
    "TaskGroupWithTasks",
    "TeamMember",
]
