"""Enumerations shared across models and the domain layer.

String-valued so the database stores readable values and API payloads are
self-explanatory.
"""

from enum import StrEnum


class Role(StrEnum):
    MANAGER = "manager"
    MEMBER = "member"


class TaskStatus(StrEnum):
    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    BLOCKED = "blocked"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class TaskEventType(StrEnum):
    CREATED = "created"
    FIELD_CHANGED = "field_changed"
    STATUS_CHANGED = "status_changed"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    DEPENDENCY_ADDED = "dependency_added"
    DEPENDENCY_REMOVED = "dependency_removed"
    COMMENTED = "commented"
