from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from job_matcher.models.enums import FeedbackType, JobStatus
from job_matcher.models.job import ApplicationStatus, Job, UserFeedback


@dataclass
class TelegramService:
    token: str
    chat_id: str
    session_factory: async_sessionmaker[AsyncSession]
    bot: Bot | None = field(init=False, default=None)
    dispatcher: Dispatcher | None = field(init=False, default=None)
    _polling_task: asyncio.Task[None] | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        if not self.token or not self.chat_id:
            return
        self.bot = Bot(self.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        self.dispatcher = Dispatcher()
        router = Router()
        self._register_handlers(router)
        self.dispatcher.include_router(router)

    @property
    def is_configured(self) -> bool:
        return self.bot is not None and self.dispatcher is not None

    async def start(self) -> None:
        if not self.is_configured or self._polling_task is not None or self.bot is None or self.dispatcher is None:
            return
        self._polling_task = asyncio.create_task(
            self.dispatcher.start_polling(self.bot, handle_signals=False, close_bot_session=False)
        )

    async def stop(self) -> None:
        if self._polling_task is not None:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass
            self._polling_task = None
        if self.bot is not None:
            await self.bot.session.close()

    async def send_job_notification(self, job: Job) -> int:
        if self.bot is None:
            raise RuntimeError("telegram bot is not configured")
        message = await self.bot.send_message(
            chat_id=self.chat_id,
            text=self._render_job_message(job),
            reply_markup=self._build_job_keyboard(job.id, job.source_url),
            disable_web_page_preview=False,
        )
        return message.message_id

    def _register_handlers(self, router: Router) -> None:
        @router.message(Command("start"))
        async def start_handler(message: Message) -> None:
            await message.answer("AI Job Aggregator bot is running.")

        @router.callback_query(F.data.startswith("status:"))
        async def status_handler(callback: CallbackQuery) -> None:
            if callback.data is None:
                return
            _, status, raw_job_id = callback.data.split(":")
            async with self.session_factory() as session:
                job = await session.get(Job, int(raw_job_id))
                if job is None:
                    await callback.answer("Job not found", show_alert=True)
                    return
                job.status = status
                session.add(ApplicationStatus(job_id=job.id, status=status, source="telegram"))
                await session.commit()
            await callback.answer(f"Updated to {status}")

        @router.callback_query(F.data.startswith("feedback:"))
        async def feedback_handler(callback: CallbackQuery) -> None:
            if callback.data is None:
                return
            _, feedback_type, raw_job_id = callback.data.split(":")
            async with self.session_factory() as session:
                job = await session.get(Job, int(raw_job_id))
                if job is None:
                    await callback.answer("Job not found", show_alert=True)
                    return
                session.add(UserFeedback(job_id=job.id, feedback_type=feedback_type, value=1))
                if feedback_type == FeedbackType.SAVE.value:
                    job.status = JobStatus.VIEWED.value
                    session.add(
                        ApplicationStatus(
                            job_id=job.id,
                            status=JobStatus.VIEWED.value,
                            source="telegram",
                            note="Saved from inline keyboard",
                        )
                    )
                await session.commit()
            await callback.answer("Feedback saved")

    @staticmethod
    def _build_job_keyboard(job_id: int, source_url: str) -> InlineKeyboardMarkup:
        builder = InlineKeyboardBuilder()
        builder.button(text="Open vacancy", url=source_url)
        builder.button(text="Dismiss", callback_data=f"status:{JobStatus.DISMISSED.value}:{job_id}")
        builder.button(text="Applied", callback_data=f"status:{JobStatus.APPLIED.value}:{job_id}")
        builder.button(text="Save", callback_data=f"feedback:{FeedbackType.SAVE.value}:{job_id}")
        builder.button(
            text="More like this", callback_data=f"feedback:{FeedbackType.MORE_LIKE_THIS.value}:{job_id}"
        )
        builder.button(
            text="Less like this", callback_data=f"feedback:{FeedbackType.LESS_LIKE_THIS.value}:{job_id}"
        )
        builder.adjust(1, 2, 1, 2)
        return builder.as_markup()

    @staticmethod
    def _render_job_message(job: Job) -> str:
        salary = "not specified"
        if job.salary_from and job.salary_to:
            salary = f"{job.salary_from} - {job.salary_to} {job.salary_currency or ''}".strip()
        elif job.salary_from:
            salary = f"from {job.salary_from} {job.salary_currency or ''}".strip()
        elif job.salary_to:
            salary = f"up to {job.salary_to} {job.salary_currency or ''}".strip()

        reasons = "\n".join(f"• {escape(reason)}" for reason in job.score_reasons[:4]) or "• no reasons"
        summary = escape((job.description_text or "")[:280])
        location = ", ".join(part for part in [job.city, job.country] if part) or "Unknown"
        return (
            f"<b>{escape(job.title)}</b>\n"
            f"<b>Company:</b> {escape(job.company_name)}\n"
            f"<b>Source:</b> {escape(job.source)}\n"
            f"<b>Salary:</b> {escape(salary)}\n"
            f"<b>Location:</b> {escape(location)} / {escape(job.remote_mode)}\n"
            f"<b>Score:</b> {job.score or 0}\n"
            f"<b>Summary:</b> {summary}\n"
            f"<b>Reasons:</b>\n{reasons}"
        )
