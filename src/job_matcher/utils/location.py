from __future__ import annotations

from job_matcher.utils.text import normalize_keyword

RUSSIA_ALIASES = {
    "russia",
    "russian federation",
    "rf",
    "россия",
    "российская федерация",
    "рф",
}


def is_russia(value: str | None) -> bool:
    if not value:
        return False
    return normalize_keyword(value) in RUSSIA_ALIASES
