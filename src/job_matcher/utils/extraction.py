from __future__ import annotations

import re
from collections.abc import Iterable

from job_matcher.models.enums import EmploymentType, ExperienceLevel, RemoteMode
from job_matcher.utils.text import normalize_keyword

TECH_KEYWORDS = [
    "typescript",
    "javascript",
    "react",
    "next.js",
    "node.js",
    "nestjs",
    "postgresql",
    "redis",
    "docker",
    "prisma",
    "graphql",
    "tailwind",
    "shadcn/ui",
    "rabbitmq",
    "kafka",
    "aws",
    "serverless",
    "ecommerce",
    "e-commerce",
    "marketplace",
    "fintech",
    "saas",
    "analytics",
    "telegram mini app",
    "api integrations",
    "performance optimization",
]


def extract_tech_tags(texts: Iterable[str | None]) -> list[str]:
    haystack = " ".join(normalize_keyword(text) for text in texts)
    found = [keyword for keyword in TECH_KEYWORDS if keyword in haystack]
    return sorted(set(found))


def detect_remote_mode(*texts: str | None) -> RemoteMode:
    haystack = " ".join(normalize_keyword(text) for text in texts)
    if any(token in haystack for token in ("remote", "удален", "удалён", "fully remote")):
        return RemoteMode.REMOTE
    if "hybrid" in haystack or "гибрид" in haystack:
        return RemoteMode.HYBRID
    if any(token in haystack for token in ("office", "офис", "on-site", "onsite")):
        return RemoteMode.OFFICE
    return RemoteMode.UNKNOWN


def detect_employment_type(*texts: str | None) -> EmploymentType:
    haystack = " ".join(normalize_keyword(text) for text in texts)
    if "полная занятость" in haystack or "full-time" in haystack or "full time" in haystack:
        return EmploymentType.FULL_TIME
    if "part-time" in haystack or "частичная занятость" in haystack:
        return EmploymentType.PART_TIME
    if "contract" in haystack or "контракт" in haystack:
        return EmploymentType.CONTRACT
    if "project" in haystack or "проект" in haystack:
        return EmploymentType.PROJECT
    if "intern" in haystack or "стаж" in haystack:
        return EmploymentType.INTERN
    return EmploymentType.UNKNOWN


def detect_experience_level(title: str | None, description: str | None) -> ExperienceLevel:
    haystack = " ".join(normalize_keyword(text) for text in (title, description))
    if re.search(r"\bintern\b|стажер|стажёр", haystack):
        return ExperienceLevel.INTERN
    if re.search(r"\bjunior\b|джуниор|младший", haystack):
        return ExperienceLevel.JUNIOR
    if re.search(r"strong middle|middle\+|middle plus|strong mid", haystack):
        return ExperienceLevel.STRONG_MIDDLE
    if re.search(r"upper[- ]middle|senior middle", haystack):
        return ExperienceLevel.UPPER_MIDDLE
    if re.search(r"\bmiddle\b|мидл|средний", haystack):
        return ExperienceLevel.MIDDLE
    if re.search(r"\bsenior\b|старший разработчик", haystack):
        return ExperienceLevel.SENIOR
    if re.search(r"\blead\b|тимлид|team lead|tech lead", haystack):
        return ExperienceLevel.LEAD
    if re.search(r"\bhead\b|руководитель", haystack):
        return ExperienceLevel.HEAD
    return ExperienceLevel.UNKNOWN
