"""Additional callback handlers.

Quiz and meetup callbacks are in their respective modules.
This file is for any other inline keyboard callbacks.
"""

import logging
from datetime import datetime

from aiogram import Router
from aiogram.types import CallbackQuery

import aiosqlite

from app.db.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(lambda c: c.data and c.data.startswith("birthday:save:"))
async def birthday_save_callback(
    callback: CallbackQuery,
    db: aiosqlite.Connection,
) -> None:
    """Handle birthday save confirmation."""
    if not callback.data or not callback.message:
        return

    await callback.answer()

    try:
        # Parse callback data: birthday:save:user_id:YYYY-MM-DD
        parts = callback.data.split(":")
        if len(parts) != 4:
            await callback.message.edit_text("❌ Ошибка: неверный формат данных")
            return

        user_id = int(parts[2])
        birth_date_str = parts[3]
        birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()

        # Save to database
        user_repo = UserRepository(db)
        await user_repo.set_birthday(user_id, birth_date)

        # Update message
        await callback.message.edit_text(
            f"✅ День рождения сохранён: {birth_date.strftime('%d.%m.%Y')}\n"
            f"Я напомню вам в этот день! 🎉"
        )

        logger.info("Saved birthday for user %d: %s", user_id, birth_date)

    except (ValueError, IndexError) as e:
        logger.exception("Failed to parse birthday callback data")
        await callback.message.edit_text("❌ Ошибка при сохранении даты")
    except Exception as e:
        logger.exception("Failed to save birthday")
        await callback.message.edit_text("❌ Не удалось сохранить дату рождения")


@router.callback_query(lambda c: c.data == "birthday:cancel")
async def birthday_cancel_callback(callback: CallbackQuery) -> None:
    """Handle birthday save cancellation."""
    await callback.answer("Отменено")
    if callback.message:
        await callback.message.edit_text("Хорошо, не буду сохранять.")
