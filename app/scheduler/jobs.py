import logging
from datetime import datetime

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import Settings
from app.db.database import Database
from app.db.repositories.reminder_repo import ReminderRepository
from app.db.repositories.user_repo import UserRepository
from app.services.birthday_service import BirthdayService
from app.utils.message_buffer import MessageBuffer

logger = logging.getLogger(__name__)


async def check_inactivity(
    bot: Bot,
    buffer: MessageBuffer,
    settings: Settings,
) -> None:
    """Check for inactive chats and suggest a quiz."""
    threshold_seconds = settings.quiz.inactivity_threshold_minutes * 60

    for chat_id in buffer.get_active_chat_ids():
        last_time = buffer.get_last_message_time(chat_id)
        if last_time is None:
            continue

        elapsed = (datetime.now() - last_time).total_seconds()
        if elapsed < threshold_seconds:
            continue

        # Don't suggest quiz if bot recently responded
        last_response = buffer._last_bot_response_time.get(chat_id)
        if last_response:
            response_elapsed = (datetime.now() - last_response).total_seconds()
            if response_elapsed < threshold_seconds:
                continue

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Да, давай!",
                        callback_data="quiz:suggest:yes",
                    ),
                    InlineKeyboardButton(
                        text="Не сейчас",
                        callback_data="quiz:suggest:no",
                    ),
                ]
            ]
        )
        try:
            await bot.send_message(
                chat_id,
                "Тишина в чате... Может квиз? 🎯",
                reply_markup=keyboard,
            )
            buffer.mark_bot_responded(chat_id)
        except Exception:
            logger.exception("Failed to send inactivity quiz to %s", chat_id)


async def check_reminders(
    bot: Bot,
    db: Database,
) -> None:
    """Fire due reminders."""
    async with db.pool.acquire() as conn:
        repo = ReminderRepository(conn)
        due = await repo.get_due()

        for reminder in due:
            try:
                await bot.send_message(
                    reminder.chat_id,
                    f"⏰ <b>Напоминание!</b>\n\n{reminder.reminder_text}",
                    parse_mode="HTML",
                )
                await repo.mark_fired(reminder.id)
            except Exception:
                logger.exception("Failed to send reminder %s", reminder.id)


async def check_birthdays(
    bot: Bot,
    db: Database,
    buffer: MessageBuffer,
) -> None:
    """Check and announce today's birthdays."""
    async with db.pool.acquire() as conn:
        service = BirthdayService()
        repo = UserRepository(conn)
        birthdays = await service.check_todays_birthdays(repo)

    if not birthdays:
        return

    message = BirthdayService.format_birthday_message(birthdays)

    for chat_id in buffer.get_active_chat_ids():
        try:
            await bot.send_message(chat_id, message, parse_mode="HTML")
        except Exception:
            logger.exception("Failed to send birthday to %s", chat_id)


async def check_upcoming_birthdays(
    bot: Bot,
    db: Database,
    buffer: MessageBuffer,
    days_ahead: int,
) -> None:
    """Check and announce upcoming birthdays (7 days or 1 day ahead)."""
    from datetime import timedelta, date

    async with db.pool.acquire() as conn:
        user_repo = UserRepository(conn)
        upcoming = await user_repo.get_upcoming_birthdays(days_ahead)

    if not upcoming:
        return

    target_date = date.today() + timedelta(days=days_ahead)

    if days_ahead == 7:
        message = f"📅 <b>Напоминаем!</b>\n\nЧерез неделю ({target_date.strftime('%d.%m')}) день рождения:\n"
    elif days_ahead == 1:
        message = f"🎂 <b>Завтра ({target_date.strftime('%d.%m')}) день рождения!</b>\n\n"
    else:
        message = f"🎉 <b>Через {days_ahead} дней ({target_date.strftime('%d.%m')}) день рождения:</b>\n\n"

    for user in upcoming:
        name = user.display_name or user.username or f"User {user.user_id}"
        message += f"• {name}\n"

    message += "\nНе забудьте поздравить! 🎁"

    for chat_id in buffer.get_active_chat_ids():
        try:
            await bot.send_message(chat_id, message, parse_mode="HTML")
        except Exception:
            logger.exception("Failed to send birthday reminder to %s", chat_id)


async def cleanup_old_messages(
    db: Database,
    settings: Settings,
) -> None:
    """Delete messages older than message_retention_days and fired reminders."""
    retention_days = settings.db.message_retention_days

    try:
        async with db.pool.acquire() as conn:
            # Delete old messages
            result = await conn.execute(
                """DELETE FROM messages
                   WHERE created_at < NOW() - INTERVAL '$1 days'""",
            )
            # Use parameterized interval
            result = await conn.execute(
                "DELETE FROM messages WHERE created_at < NOW() - make_interval(days => $1)",
                retention_days,
            )
            deleted_messages = int(result.split()[-1]) if result else 0

            if deleted_messages > 0:
                logger.info(
                    "Cleaned up %d messages older than %d days",
                    deleted_messages,
                    retention_days,
                )

            # Delete fired reminders (already sent)
            result = await conn.execute(
                "DELETE FROM reminders WHERE is_fired = TRUE",
            )
            deleted_reminders = int(result.split()[-1]) if result else 0

            if deleted_reminders > 0:
                logger.info("Cleaned up %d fired reminders", deleted_reminders)

            # Also clean up old stats (keep last 30 days)
            result = await conn.execute(
                "DELETE FROM bot_daily_stats WHERE date < NOW() - INTERVAL '30 days'",
            )
            deleted_stats = int(result.split()[-1]) if result else 0

            if deleted_stats > 0:
                logger.info("Cleaned up %d old stats records", deleted_stats)

    except Exception:
        logger.exception("Failed to cleanup old data")


def register_jobs(
    scheduler: AsyncIOScheduler,
    bot: Bot,
    db: Database,
    buffer: MessageBuffer,
    settings: Settings,
) -> None:
    # Check inactivity every 30 minutes
    scheduler.add_job(
        check_inactivity,
        "interval",
        minutes=30,
        kwargs={"bot": bot, "buffer": buffer, "settings": settings},
    )

    # Check reminders every minute
    scheduler.add_job(
        check_reminders,
        "interval",
        minutes=1,
        kwargs={"bot": bot, "db": db},
    )

    # Check birthdays daily at 9:00
    scheduler.add_job(
        check_birthdays,
        "cron",
        hour=9,
        minute=0,
        kwargs={"bot": bot, "db": db, "buffer": buffer},
    )

    # Birthday reminder: 7 days ahead at 10:00
    scheduler.add_job(
        check_upcoming_birthdays,
        "cron",
        hour=10,
        minute=0,
        kwargs={"bot": bot, "db": db, "buffer": buffer, "days_ahead": 7},
    )

    # Birthday reminder: 1 day ahead at 18:00
    scheduler.add_job(
        check_upcoming_birthdays,
        "cron",
        hour=18,
        minute=0,
        kwargs={"bot": bot, "db": db, "buffer": buffer, "days_ahead": 1},
    )

    # Cleanup old messages weekly on Sunday at 3:00 AM
    scheduler.add_job(
        cleanup_old_messages,
        "cron",
        day_of_week="sun",
        hour=3,
        minute=0,
        kwargs={"db": db, "settings": settings},
    )
