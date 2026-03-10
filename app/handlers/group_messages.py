import asyncio
import logging
import random

from aiogram import F, Router
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import asyncpg

from app.config import Settings
from app.db.repositories.link_repo import LinkRepository
from app.db.repositories.reminder_repo import ReminderRepository
from app.db.repositories.stats_repo import StatsRepository
from app.db.repositories.user_repo import UserRepository
from app.services.ai_analyzer import AIAnalyzer
from app.services.birthday_parser import BirthdayParser
from app.services.link_collector import LinkCollector
from app.services.meetup_detector import MeetupDetector
from app.services.reminder_service import ReminderService
from app.utils.message_buffer import MessageBuffer
from app.utils.text_utils import extract_urls

logger = logging.getLogger(__name__)

router = Router()


@router.message(F.text & F.chat.type.in_({"group", "supergroup"}))
async def handle_group_message(
    message: Message,
    db: asyncpg.Connection,
    message_buffer: MessageBuffer,
    ai_analyzer: AIAnalyzer,
    birthday_parser: BirthdayParser,
    meetup_detector: MeetupDetector,
    reminder_service: ReminderService,
    link_collector: LinkCollector,
    settings: Settings,
    should_analyze: bool = False,
    trigger_type: str | None = None,
    rate_limited: bool = False,
) -> None:
    if not message.text or not message.from_user:
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    # Collect links silently
    if extract_urls(message.text):
        repo = LinkRepository(db)
        await link_collector.collect_and_save(message.text, chat_id, user_id, repo)

    # Check daily cap for proactive messages only
    if should_analyze and not rate_limited and trigger_type is None:
        stats_repo = StatsRepository(db)
        daily_count = await stats_repo.get_daily_proactive_count(chat_id)
        if daily_count >= settings.rate_limit.daily_proactive_cap:
            return

    # Handle direct trigger (keyword detected)
    if trigger_type == "meetup" and not rate_limited:
        # Check if bot already responded recently (5 minutes cooldown)
        if message_buffer.was_bot_active_recently(chat_id, seconds=300):
            # Check if this is about a DIFFERENT event
            last_context = message_buffer.get_last_meetup_context(chat_id)
            if last_context:
                is_same = await meetup_detector.is_same_event(last_context, message.text)
                if is_same:
                    # Same event, skip to avoid spam
                    return
            else:
                # No previous context, skip
                return

        recent = message_buffer.get_recent(chat_id, n=15)
        response = await meetup_detector.generate_meetup_response(recent)
        if response:
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📊 Создать опрос",
                            callback_data="meetup:create_poll",
                        ),
                        InlineKeyboardButton(
                            text="Не нужно",
                            callback_data="meetup:skip",
                        ),
                    ]
                ]
            )
            await message.answer(response, reply_markup=keyboard)
            message_buffer.mark_bot_responded(chat_id)
            message_buffer.mark_analyzed(chat_id)
            # Store current message as context for future comparison
            message_buffer.set_last_meetup_context(chat_id, message.text)

            stats_repo = StatsRepository(db)
            await stats_repo.increment_proactive(chat_id)
            return

    if trigger_type == "reminder" and not rate_limited:
        repo = ReminderRepository(db)
        reminder = await reminder_service.parse_and_save(
            message.text, chat_id, user_id, repo
        )
        if reminder:
            remind_str = reminder.remind_at.strftime("%d.%m.%Y в %H:%M")
            await message.reply(
                f"⏰ Запомнил! Напомню: «{reminder.reminder_text}» — {remind_str}"
            )
            message_buffer.mark_bot_responded(chat_id)
            message_buffer.mark_analyzed(chat_id)
            stats_repo = StatsRepository(db)
            await stats_repo.increment_proactive(chat_id)
            return
        else:
            # If it's a mention, we'll let it handle below in the generic mention block
            # If it's just a keyword and parsing failed, we do nothing to avoid false positives
            if trigger_type != "reminder": # This case shouldn't happen with current logic but for safety
                pass 
            elif "бот" in message.text.lower():
                # It was intended for bot, but parsing failed. Let's fall through to mention handler
                trigger_type = "mention" 
            else:
                return

    if trigger_type == "quiz" and not rate_limited:
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
        await message.answer("Хотите сыграть в квиз? 🎯", reply_markup=keyboard)
        message_buffer.mark_bot_responded(chat_id)
        message_buffer.mark_analyzed(chat_id)

        stats_repo = StatsRepository(db)
        await stats_repo.increment_proactive(chat_id)
        return

    if trigger_type == "birthday" and not rate_limited:
        # Parse birthday mention from message
        birthday_mention = await birthday_parser.parse_birthday_mention(message.text)

        if birthday_mention and birthday_mention.birth_date:
            user_repo = UserRepository(db)

            # Determine whose birthday it is
            if birthday_mention.is_author:
                # Author's birthday
                target_user_id = user_id
                target_name = message.from_user.full_name
            else:
                # Someone else's birthday mentioned - ask for clarification
                # Store date in callback data for later use
                callback_data = f"birthday:ask:{birthday_mention.birth_date.isoformat()}"
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="❌ Отмена",
                                callback_data="birthday:cancel",
                            ),
                        ]
                    ]
                )

                await message.reply(
                    f"🎂 Вижу упоминание дня рождения ({birthday_mention.birth_date.strftime('%d.%m.%Y')}).\n\n"
                    f"<b>У кого день рождения?</b>\n"
                    f"Попросите этого пользователя указать дату самому через команду:\n"
                    f"<code>/birthday {birthday_mention.birth_date.strftime('%d.%m.%Y')}</code>",
                    reply_markup=keyboard,
                )

                message_buffer.mark_bot_responded(chat_id)
                message_buffer.mark_analyzed(chat_id)
                stats_repo = StatsRepository(db)
                await stats_repo.increment_proactive(chat_id)
                return

            # Create confirmation keyboard
            callback_data = f"birthday:save:{target_user_id}:{birthday_mention.birth_date.isoformat()}"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="✅ Да, сохранить",
                            callback_data=callback_data,
                        ),
                        InlineKeyboardButton(
                            text="❌ Нет",
                            callback_data="birthday:cancel",
                        ),
                    ]
                ]
            )

            await message.reply(
                f"🎂 Вижу что у {target_name} день рождения {birthday_mention.birth_date.strftime('%d.%m.%Y')}.\n"
                f"Сохранить эту дату?",
                reply_markup=keyboard,
            )
            message_buffer.mark_bot_responded(chat_id)
            message_buffer.mark_analyzed(chat_id)

            stats_repo = StatsRepository(db)
            await stats_repo.increment_proactive(chat_id)
            return

    # AI analysis for accumulated messages
    # Only for specific actions: meetup coordination or reminder detection
    # General "question" responses are disabled to avoid being too chatty
    if should_analyze and not rate_limited:
        recent = message_buffer.get_since_last_analysis(chat_id)
        if not recent:
            recent = message_buffer.get_recent(chat_id, n=20)

        result = await ai_analyzer.analyze_messages(recent)
        message_buffer.mark_analyzed(chat_id)

        if result and result.should_respond:
            if result.response_type == "meetup":
                response = await meetup_detector.generate_meetup_response(recent)
                if response:
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="📊 Создать опрос",
                                    callback_data="meetup:create_poll",
                                ),
                                InlineKeyboardButton(
                                    text="Не нужно",
                                    callback_data="meetup:skip",
                                ),
                            ]
                        ]
                    )
                    await message.answer(response, reply_markup=keyboard)
                    message_buffer.mark_bot_responded(chat_id)
                    stats_repo = StatsRepository(db)
                    await stats_repo.increment_proactive(chat_id)
            elif result.response_type == "reminder":
                repo = ReminderRepository(db)
                reminder = await reminder_service.parse_and_save(
                    message.text, chat_id, user_id, repo
                )
                if reminder:
                    remind_str = reminder.remind_at.strftime("%d.%m.%Y в %H:%M")
                    await message.reply(
                        f"⏰ Запомнил! Напомню: «{reminder.reminder_text}» — {remind_str}"
                    )
                    message_buffer.mark_bot_responded(chat_id)
                    stats_repo = StatsRepository(db)
                    await stats_repo.increment_proactive(chat_id)
            # Note: "question" type responses are intentionally disabled
            # Bot only responds proactively for specific actions (meetup/reminder/quiz)

    # Handle direct mention or reply
    if trigger_type == "mention" and not rate_limited:
        # Check if bot already responded very recently (30 seconds cooldown)
        # This prevents spamming when user quotes bot messages or replies multiple times
        cooldown_seconds = 30
        if message_buffer.was_bot_active_recently(chat_id, seconds=cooldown_seconds):
            remaining = message_buffer.get_cooldown_remaining(chat_id, cooldown_seconds)
            logger.debug(f"Skipping mention response in {chat_id} - bot was active recently ({remaining}s remaining)")

            # Notify user about cooldown only if we haven't already scheduled a notification
            if not message_buffer.has_active_cooldown_task(chat_id):
                cooldown_messages = [
                    f"⏸️ Стоп, стоп, дайте отдохнуть! Я на перекуре, вернусь через {remaining} секунд.",
                    f"⏸️ Опа, кажется я вам слишком нравлюсь! На кулдауне {remaining} секунд, потерпите.",
                    f"⏸️ Я не железный, знаете ли! Отдыхаю {remaining} секунд, потом продолжим беседу.",
                    f"⏸️ Тайм-аут! {remaining} секунд на восстановление. Не скучайте без меня.",
                ]
                await message.reply(random.choice(cooldown_messages))

                # Schedule a notification when cooldown ends
                async def notify_return():
                    try:
                        await asyncio.sleep(remaining)
                        return_messages = [
                            "✅ Ну всё, я вернулся! Соскучились?",
                            "✅ Отдохнул, теперь готов к новым подвигам!",
                            "✅ Батарейки подзарядил, снова в строю!",
                            "✅ Перекур окончен, можно продолжать.",
                        ]
                        await message.answer(random.choice(return_messages))
                    except asyncio.CancelledError:
                        pass  # Task was cancelled, no problem
                    finally:
                        message_buffer.clear_cooldown_task(chat_id)

                task = asyncio.create_task(notify_return())
                message_buffer.set_cooldown_task(chat_id, task)

            return

        recent = message_buffer.get_recent(chat_id, n=15)

        # Send a placeholder message to let the user know the bot is thinking
        thinking_msg = await message.reply("🤔 Секунду, читаю контекст и думаю над ответом...")

        # If mention contains reminder keywords, try to parse it as reminder first
        text_lower = message.text.lower()
        if any(kw in text_lower for kw in ["напомни", "запомни", "не забудь"]):
            repo = ReminderRepository(db)
            reminder = await reminder_service.parse_and_save(
                message.text, chat_id, user_id, repo
            )
            if reminder:
                remind_str = reminder.remind_at.strftime("%d.%m.%Y в %H:%M")
                await thinking_msg.edit_text(
                    f"⏰ Запомнил! Напомню: «{reminder.reminder_text}» — {remind_str}"
                )
                message_buffer.mark_bot_responded(chat_id)
                message_buffer.mark_analyzed(chat_id)
                return

        # Force the AI to answer specifically
        response_text = await ai_analyzer.generate_direct_response(recent)

        # We always reply if directly mentioned, even if AI thinks it shouldn't normally proactively respond
        if response_text:
            await thinking_msg.edit_text(response_text)
        else:
            # Fallback if AI didn't generate a good response
            await thinking_msg.edit_text("Слушаю! Что интересует?")

        message_buffer.mark_bot_responded(chat_id)
        message_buffer.mark_analyzed(chat_id)
        # Note: Direct mentions don't count towards daily proactive limit
