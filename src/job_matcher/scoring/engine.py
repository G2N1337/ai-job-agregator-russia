from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from job_matcher.models.enums import ExperienceLevel, RemoteMode
from job_matcher.schemas.domain import NormalizedJob, ScoreResult
from job_matcher.utils.text import normalize_keyword


@dataclass(slots=True)
class ScoringRules:
    title_weights: dict[str, int]
    positive_keywords: dict[str, int]
    negative_keywords: dict[str, int]
    remote_mode_weights: dict[str, int]
    seniority_weights: dict[str, int]
    must_have_groups: list[dict[str, Any]]
    penalties: dict[str, int]
    max_score: int
    min_score: int


class ScoringEngine:
    def __init__(self, rules_path: Path) -> None:
        self.rules_path = rules_path
        self.rules = self._load_rules(rules_path)

    def _load_rules(self, rules_path: Path) -> ScoringRules:
        payload = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
        return self._load_rules_from_payload(payload)

    def _load_rules_from_payload(self, payload: dict[str, Any]) -> ScoringRules:
        return ScoringRules(
            title_weights=payload["title_weights"],
            positive_keywords=payload["positive_keywords"],
            negative_keywords=payload["negative_keywords"],
            remote_mode_weights=payload["remote_mode_weights"],
            seniority_weights=payload["seniority_weights"],
            must_have_groups=payload["must_have_groups"],
            penalties=payload["penalties"],
            max_score=payload["max_score"],
            min_score=payload["min_score"],
        )

    def reload_from_yaml(self, rules_yaml: str) -> None:
        payload = yaml.safe_load(rules_yaml)
        self.rules = self._load_rules_from_payload(payload)

    def score(self, job: NormalizedJob) -> ScoreResult:
        reasons: list[str] = []
        details: dict[str, Any] = {"matched_keywords": [], "penalty_keywords": []}
        score = 35
        haystack = normalize_keyword(
            " ".join(
                [
                    job.title,
                    job.company_name,
                    job.description_text or "",
                    " ".join(job.tech_tags_extracted),
                    job.search_query or "",
                ]
            )
        )

        title_score = 0
        for title, weight in self.rules.title_weights.items():
            if title in haystack:
                title_score = max(title_score, weight)
        if title_score:
            score += title_score
            reasons.append(f"+{title_score} title alignment")

        for group in self.rules.must_have_groups:
            if all(term in haystack for term in group["terms"]):
                score += int(group["weight"])
                reasons.append(f"+{group['weight']} {group['label']}")

        for keyword, weight in self.rules.positive_keywords.items():
            if keyword in haystack:
                score += weight
                details["matched_keywords"].append(keyword)
                reasons.append(f"+{weight} {keyword}")

        for keyword, weight in self.rules.negative_keywords.items():
            if keyword in haystack:
                score += weight
                details["penalty_keywords"].append(keyword)
                reasons.append(f"{weight} {keyword}")

        remote_weight = self.rules.remote_mode_weights.get(job.remote_mode.value, 0)
        if remote_weight:
            score += remote_weight
            if job.remote_mode == RemoteMode.OFFICE:
                reasons.append(f"{remote_weight:+d} office-only")
            else:
                reasons.append(f"{remote_weight:+d} remote mode {job.remote_mode.value}")

        seniority_weight = self.rules.seniority_weights.get(job.experience_level.value, 0)
        if seniority_weight:
            score += seniority_weight
            reasons.append(f"{seniority_weight:+d} seniority {job.experience_level.value}")

        if job.remote_mode == RemoteMode.OFFICE:
            office_penalty = self.rules.penalties["office_only"]
            if office_penalty not in (0, remote_weight):
                score += office_penalty
                reasons.append(f"{office_penalty} office-only")

        if job.experience_level in (ExperienceLevel.LEAD, ExperienceLevel.HEAD):
            mismatch_penalty = self.rules.penalties["strong_seniority_mismatch"]
            score += mismatch_penalty
            reasons.append(f"{mismatch_penalty} seniority mismatch")

        bounded = max(self.rules.min_score, min(self.rules.max_score, score))
        return ScoreResult(score=bounded, reasons=self._dedupe_reasons(reasons), details=details)

    @staticmethod
    def _dedupe_reasons(reasons: list[str]) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for reason in reasons:
            if reason not in seen:
                unique.append(reason)
                seen.add(reason)
        return unique[:20]
