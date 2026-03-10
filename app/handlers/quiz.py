import asyncio
import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import asyncpg

from app.db.repositories.quiz_repo import QuizRepository
from app.db.repositories.user_repo import UserRepository
from app.services.quiz_service import QuizService
from app.utils.message_buffer import MessageBuffer

logger = logging.getLogger(__name__)

router = Router()

ANSWER_LABELS = ["A", "B", "C", "D"]


def build_quiz_keyboard(quiz_id: str, options: list[str]) -> InlineKeyboardMarkup:
    buttons = []
    for i, option in enumerate(options):
        label = ANSWER_LABELS[i] if i < len(ANSWER_LABELS) else str(i + 1)
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{label}. {option}",
                    callback_data=f"quiz:{quiz_id}:{i}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def wait_and_finish_quiz(
    chat_id: int,
    quiz_id: str,
    quiz_service: QuizService,
    bot: Bot,
    db: asyncpg.Connection,
    timeout: int = 30,
) -> None:
    await asyncio.sleep(timeout)
    session = quiz_service.get_active_session(chat_id)
    if session and session.id == quiz_id and not session.finished:
        finished = quiz_service.finish_quiz(chat_id)
        if finished:
            repo = QuizRepository(db)
            await quiz_service.save_scores(finished, repo)

            user_repo = UserRepository(db)
            usernames = {}
            for uid in finished.answers:
                user = await user_repo.get(uid)
                usernames[uid] = user.username or user.display_name if user else f"user_{uid}"
                
            results = finished.get_results_text(usernames)
            try:
                await bot.send_message(
                    chat_id,
                    f"⏱ <b>Время вышло!</b>\n\n📊 <b>Результаты квиза:</b>\n\n{results}",
                    parse_mode="HTML",
                )
            except Exception:
                logger.exception("Failed to send scheduled quiz results")


@router.message(Command("quiz"))
async def cmd_quiz(
    message: Message,
    bot: Bot,
    db: asyncpg.Connection,
    quiz_service: QuizService,
    message_buffer: MessageBuffer,
) -> None:
    chat_id = message.chat.id

    existing = quiz_service.get_active_session(chat_id)
    if existing:
        await message.answer("Квиз уже идёт! Ответьте на текущий вопрос.")
        return

    # Show "Creating question..." message
    status_msg = await message.answer("🎯 Создается вопрос...")

    # Use recent chat context for relevant questions
    recent = message_buffer.get_recent(chat_id, n=20)
    context = ""
    if recent:
        context = "\n".join(f"{m.username}: {m.text}" for m in recent[-10:])

    session = await quiz_service.create_quiz(chat_id, context)
    if not session:
        await status_msg.edit_text("Не удалось сгенерировать квиз. Попробуйте ещё раз.")
        return

    keyboard = build_quiz_keyboard(session.id, session.options)
    # Update the message with the actual quiz question
    await status_msg.edit_text(
        f"🎯 <b>Квиз!</b> У вас есть 30 секунд на ответ.\n\n{session.question}",
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    # Schedule auto-finish
    asyncio.create_task(
        wait_and_finish_quiz(chat_id, session.id, quiz_service, bot, db)
    )

@router.message(Command("quiz_scores"))
async def cmd_quiz_scores(
    message: Message,
    db: asyncpg.Connection,
) -> None:
    repo = QuizRepository(db)
    leaderboard = await repo.get_leaderboard(message.chat.id)
    if not leaderboard:
        await message.answer("Пока нет результатов квизов.")
        return

    lines = ["🏆 <b>Таблица лидеров:</b>\n"]
    medals = ["🥇", "🥈", "🥉"]
    user_repo = UserRepository(db)
    for i, entry in enumerate(leaderboard):
        medal = medals[i] if i < 3 else f"{i + 1}."
        user = await user_repo.get(entry["user_id"])
        name = user.username or user.display_name if user else f"user_{entry['user_id']}"
        
        accuracy = (
            round(entry["correct_answers"] / entry["quizzes_played"] * 100)
            if entry["quizzes_played"]
            else 0
        )
        lines.append(
            f"{medal} <b>{name}</b> — "
            f"{entry['total_points']} очков "
            f"({accuracy}% правильных)"
        )

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.callback_query(lambda c: c.data == "quiz:suggest:yes")
async def quiz_suggest_yes(
    callback: CallbackQuery,
    bot: Bot,
    db: asyncpg.Connection,
    quiz_service: QuizService,
    message_buffer: MessageBuffer,
) -> None:
    if not callback.message:
        return

    chat_id = callback.message.chat.id
    await callback.answer()

    # Show "Creating question..." message
    await callback.message.edit_text("🎯 Создается вопрос...")

    recent = message_buffer.get_recent(chat_id, n=20)
    context = "\n".join(f"{m.username}: {m.text}" for m in recent[-10:]) if recent else ""

    session = await quiz_service.create_quiz(chat_id, context)
    if not session:
        await callback.message.edit_text("Не удалось создать квиз.")
        return

    keyboard = build_quiz_keyboard(session.id, session.options)
    # Update the message with the actual quiz question
    await callback.message.edit_text(
        f"🎯 <b>Квиз!</b> У вас есть 30 секунд на ответ.\n\n{session.question}",
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    # Schedule auto-finish
    asyncio.create_task(
        wait_and_finish_quiz(chat_id, session.id, quiz_service, bot, db)
    )

@router.callback_query(lambda c: c.data == "quiz:suggest:no")
async def quiz_suggest_no(callback: CallbackQuery) -> None:
    await callback.answer("Ок, в другой раз!")
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)


@router.callback_query(lambda c: c.data and c.data.startswith("quiz:"))
async def quiz_answer_callback(
    callback: CallbackQuery,
    quiz_service: QuizService,
    db: asyncpg.Connection,
) -> None:
    if not callback.data or not callback.from_user:
        return

    parts = callback.data.split(":")
    if len(parts) != 3:
        return

    _, quiz_id, answer_str = parts
    try:
        answer_index = int(answer_str)
    except ValueError:
        return

    chat_id = callback.message.chat.id if callback.message else 0
    user_id = callback.from_user.id

    session = quiz_service.get_active_session(chat_id)
    if not session or session.id != quiz_id:
        await callback.answer("Этот квиз уже завершён.", show_alert=False)
        return

    recorded = quiz_service.record_answer(chat_id, user_id, answer_index)
    if not recorded:
        await callback.answer("Ты уже ответил!", show_alert=False)
        return

    is_correct = answer_index == session.correct_index
    await callback.answer(
        "Правильно! ✅" if is_correct else "Неправильно ❌",
        show_alert=False,
    )

    # Auto-finish after 5 answers
    if len(session.answers) >= 5:
        finished = quiz_service.finish_quiz(chat_id)
        if finished and callback.message:
            # Save scores
            repo = QuizRepository(db)
            await quiz_service.save_scores(finished, repo)

            user_repo = UserRepository(db)
            usernames = {}
            for uid in finished.answers:
                user = await user_repo.get(uid)
                usernames[uid] = user.username or user.display_name if user else f"user_{uid}"

            results = finished.get_results_text(usernames)
            await callback.message.answer(
                f"📊 <b>Результаты квиза:</b>\n\n{results}",
                parse_mode="HTML",
            )
