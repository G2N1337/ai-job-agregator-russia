from __future__ import annotations

from abc import ABC, abstractmethod

from job_matcher.schemas.domain import CollectorResult


class BaseCollector(ABC):
    source: str
    experimental: bool = False

    @abstractmethod
    async def collect(self, query: str) -> CollectorResult:
        raise NotImplementedError
