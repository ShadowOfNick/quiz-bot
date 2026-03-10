import logging
from datetime import date, datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import asyncpg

from app.db.repositories.link_repo import LinkRepository
from app.db.repositories.reminder_repo import ReminderRepository
from app.db.repositories.stats_repo import StatsRepository
from app.db.repositories.user_repo import UserRepository
from app.services.reminder_service import ReminderService
from app.services.stats_service import StatsService

logger = logging.getLogger(__name__)

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Привет! Я бот-помощник для вашей группы.\n\n"
        "Вот что я умею:\n"
        "🎯 /quiz — запустить мини-квиз\n"
        "🏆 /quiz_scores — таблица лидеров квиза\n"
        "📊 /stats — статистика группы\n"
        "🎂 /birthday ДД.ММ.ГГГГ — указать день рождения\n"
        "🔗 /links — последние ссылки из чата\n"
        "❓ /help — эта справка\n\n"
        "Также я слежу за обсуждением и могу помочь "
        "организовать встречу или напомнить о чём-то."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>Доступные команды:</b>\n\n"
        "🎯 /quiz — мини-квиз для группы\n"
        "🏆 /quiz_scores — таблица лидеров квиза\n"
        "📊 /stats — статистика активности за неделю\n"
        "🎂 /birthday ДД.ММ.ГГГГ — указать свой день рождения\n"
        "🔗 /links — последние сохранённые ссылки\n\n"
        "<b>Автоматические функции:</b>\n"
        "• Предлагаю создать опрос при обсуждении встреч\n"
        "• Предлагаю квиз при долгой тишине\n"
        "• Распознаю напоминания (\"напомни мне завтра...\")\n"
        "• Собираю ссылки из чата",
        parse_mode="HTML",
    )


@router.message(Command("stats"))
async def cmd_stats(
    message: Message,
    db: asyncpg.Connection,
    stats_service: StatsService,
) -> None:
    repo = StatsRepository(db)
    text = await stats_service.format_stats(message.chat.id, repo)
    await message.answer(text, parse_mode="HTML")


@router.message(Command("birthday"))
async def cmd_birthday(
    message: Message,
    db: asyncpg.Connection,
) -> None:
    if not message.from_user:
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "Укажи дату рождения в формате ДД.ММ.ГГГГ\n"
            "Пример: /birthday 15.03.1990"
        )
        return

    try:
        birthday = datetime.strptime(args[1].strip(), "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Неверный формат даты. Используй ДД.ММ.ГГГГ")
        return

    repo = UserRepository(db)
    await repo.set_birthday(message.from_user.id, birthday)
    await message.answer(
        f"🎂 Запомнил! Твой день рождения: {birthday.strftime('%d.%m.%Y')}"
    )


@router.message(Command("links"))
async def cmd_links(
    message: Message,
    db: asyncpg.Connection,
) -> None:
    repo = LinkRepository(db)
    links = await repo.get_recent(message.chat.id, limit=15)
    if not links:
        await message.answer("Пока ссылок не сохранено.")
        return

    lines = ["🔗 <b>Последние ссылки:</b>\n"]
    for link in links:
        title = link.title or link.url
        ts = link.created_at.strftime("%d.%m %H:%M")
        lines.append(f"• <a href=\"{link.url}\">{title}</a> ({ts})")

    await message.answer("\n".join(lines), parse_mode="HTML", disable_web_page_preview=True)
