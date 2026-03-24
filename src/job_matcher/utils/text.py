from __future__ import annotations

import hashlib
import re
from html import unescape

from bs4 import BeautifulSoup
from slugify import slugify

WHITESPACE_RE = re.compile(r"\s+")


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "html.parser")
    return normalize_whitespace(unescape(soup.get_text(" ", strip=True)))


def normalize_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return WHITESPACE_RE.sub(" ", value).strip()


def normalize_keyword(value: str | None) -> str:
    return normalize_whitespace((value or "").lower())


def canonicalize_url(url: str | None) -> str | None:
    if not url:
        return None
    cleaned = re.sub(r"[?#].*$", "", url.strip())
    return cleaned.rstrip("/") or cleaned


def build_fingerprint(
    title: str,
    company_name: str,
    salary_from: str,
    salary_to: str,
    description_text: str,
) -> str:
    normalized = " | ".join(
        [
            slugify(title.lower()),
            slugify(company_name.lower()),
            salary_from,
            salary_to,
            slugify(description_text[:500].lower()),
        ]
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:32]
