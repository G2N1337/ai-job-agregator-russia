from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_matcher.models.enums import NotificationStatus
from job_matcher.models.job import Job, Notification
from job_matcher.telegram.bot import TelegramService
from job_matcher.utils.datetime import utcnow


@dataclass(slots=True)
class NotificationService:
    telegram_service: TelegramService
    score_threshold: int
    demo_mode: bool

    async def notify_if_needed(self, session: AsyncSession, job: Job) -> bool:
        if job.duplicate_of_id is not None:
            return False
        if (job.score or 0) < self.score_threshold:
            return False
        existing = await session.scalar(
            select(Notification).where(
                Notification.job_id == job.id,
                Notification.channel == "telegram",
                Notification.status == NotificationStatus.SENT.value,
            )
        )
        if existing is not None:
            return False

        notification = Notification(
            job_id=job.id,
            channel="telegram",
            recipient=self.telegram_service.chat_id,
            status=NotificationStatus.PENDING.value,
        )
        session.add(notification)
        await session.flush()

        if self.telegram_service.is_configured:
            try:
                message_id = await self.telegram_service.send_job_notification(job)
            except Exception as exc:
                notification.status = NotificationStatus.FAILED.value
                notification.error_message = str(exc)
                return False
            notification.status = NotificationStatus.SENT.value
            notification.message_id = str(message_id)
            notification.sent_at = utcnow()
            return True

        if self.demo_mode:
            notification.status = NotificationStatus.SENT.value
            notification.message_id = f"demo-{job.id}"
            notification.sent_at = utcnow()
            return True

        notification.status = NotificationStatus.FAILED.value
        notification.error_message = "telegram disabled"
        return False
