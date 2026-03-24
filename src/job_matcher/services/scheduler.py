from __future__ import annotations

from dataclasses import dataclass

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from job_matcher.services.collection_service import CollectionService


@dataclass(slots=True)
class SchedulerService:
    scheduler: AsyncIOScheduler
    collection_service: CollectionService
    interval_minutes: int

    def start(self) -> None:
        if self.scheduler.running:
            return
        self.scheduler.add_job(
            self.collection_service.collect_all,
            trigger=IntervalTrigger(minutes=self.interval_minutes),
            id="collect-jobs",
            replace_existing=True,
            max_instances=1,
        )
        self.scheduler.start()

    def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
