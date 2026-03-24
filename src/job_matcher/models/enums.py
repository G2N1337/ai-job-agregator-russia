from __future__ import annotations

from enum import StrEnum


class RemoteMode(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    OFFICE = "office"
    UNKNOWN = "unknown"


class EmploymentType(StrEnum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    PROJECT = "project"
    INTERN = "intern"
    UNKNOWN = "unknown"


class ExperienceLevel(StrEnum):
    INTERN = "intern"
    JUNIOR = "junior"
    MIDDLE = "middle"
    MIDDLE_PLUS = "middle_plus"
    STRONG_MIDDLE = "strong_middle"
    UPPER_MIDDLE = "upper_middle"
    SENIOR = "senior"
    LEAD = "lead"
    HEAD = "head"
    UNKNOWN = "unknown"


class JobStatus(StrEnum):
    NEW = "new"
    VIEWED = "viewed"
    DISMISSED = "dismissed"
    APPLIED = "applied"
    INTERVIEW = "interview"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class FeedbackType(StrEnum):
    MORE_LIKE_THIS = "more_like_this"
    LESS_LIKE_THIS = "less_like_this"
    SAVE = "save"
