import logging
from datetime import datetime
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.config import AnalysisSettings
from app.db.models import Message as DbMessage
from app.db.repositories.message_repo import MessageRepository
from app.db.repositories.user_repo import UserRepository
from app.db.models import User
from app.utils.message_buffer import BufferedMessage, MessageBuffer
from app.utils.text_utils import extract_urls

logger = logging.getLogger(__name__)

MEETUP_KEYWORDS = [
    "давайте соберёмся", "давайте соберемся", "кто свободен",
    "может встретимся", "погнали тусить", "пойдём", "пойдем",
    "кто за", "есть планы", "свободен в", "может соберёмся",
    "может соберемся", "давайте встретимся", "куда пойдём",
    "куда пойдем", "во сколько встречаемся", "встреча", "встретиться",
    "кто хочет", "кто пойдет", "кто идет", "кто пойдёт", "кто идёт",
    "кто с нами", "кто составит", "кто может", "кто придет", "кто придёт"
]

REMINDER_KEYWORDS = [
    "напомни", "напомните", "не забыть", "не забудь",
    "запомни", "запомните", "напоминание",
]

QUIZ_KEYWORDS = [
    "викторину", "мини-квиз", "мини квиз", "давай квиз",
    "сделай квиз", "создай квиз", "хочу квиз", "поиграть в квиз",
    "сыграть в квиз", "запусти квиз", "начни квиз"
]

BIRTHDAY_KEYWORDS = [
    "день рождения", "день рожденья", "др ", " др,",
    "мой др", "моё др", "скоро др", "завтра др",
    "родился", "родилась", "исполняется", "исполнится"
]


def detect_trigger(text: str) -> str | None:
    text_lower = text.lower().strip()

    # Special case: standalone "квиз" or "квиз?" is a direct request
    if text_lower in ("квиз", "квиз?", "квиз!"):
        return "quiz"

    for kw in MEETUP_KEYWORDS:
        if kw in text_lower:
            return "meetup"
    for kw in REMINDER_KEYWORDS:
        if kw in text_lower:
            return "reminder"

    # Quiz keywords: check for negation
    for kw in QUIZ_KEYWORDS:
        if kw in text_lower:
            # Check if there's a negation word before the keyword
            idx = text_lower.find(kw)
            # Get text before the keyword (up to 10 chars back)
            before = text_lower[max(0, idx-10):idx]
            if any(neg in before for neg in ["не ", "нет", "ни "]):
                continue  # Skip if negation found
            return "quiz"

    for kw in BIRTHDAY_KEYWORDS:
        if kw in text_lower:
            return "birthday"
    return None


class MessageCollectorMiddleware(BaseMiddleware):
    def __init__(self, buffer: MessageBuffer, settings: AnalysisSettings):
        self._buffer = buffer
        self._settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or not event.text:
            return await handler(event, data)

        chat_type = event.chat.type
        if chat_type not in ("group", "supergroup"):
            return await handler(event, data)

        # Save to in-memory buffer
        username = event.from_user.username or ""
        display_name = event.from_user.full_name if event.from_user else ""
        buffered = BufferedMessage(
            chat_id=event.chat.id,
            user_id=event.from_user.id if event.from_user else 0,
            username=username or display_name,
            text=event.text,
            timestamp=datetime.now(),
            message_id=event.message_id,
        )
        self._buffer.add(buffered)

        # Persist to DB
        db_conn = data.get("db")
        if db_conn:
            has_links = bool(extract_urls(event.text))
            msg = DbMessage(
                chat_id=event.chat.id,
                user_id=event.from_user.id if event.from_user else 0,
                message_id=event.message_id,
                text=event.text,
                username=username,
                display_name=display_name,
                reply_to_message_id=(
                    event.reply_to_message.message_id
                    if event.reply_to_message
                    else None
                ),
                has_links=has_links,
            )
            try:
                repo = MessageRepository(db_conn)
                await repo.save(msg)

                # Upsert user
                if event.from_user:
                    user_repo = UserRepository(db_conn)
                    await user_repo.upsert(
                        User(
                            user_id=event.from_user.id,
                            username=username,
                            display_name=display_name,
                        )
                    )
            except Exception:
                logger.exception("Failed to save message to DB")

        # Detect triggers and pass info to handler
        trigger = detect_trigger(event.text)
        
        # Check if bot is mentioned or replied to
        bot_user = None
        bot_instance = data.get("bot") or getattr(event, "bot", None)
        if bot_instance:
            try:
                bot_user = await bot_instance.get_me()
            except Exception:
                logger.exception("Failed to get bot user")
                pass
        bot_username = bot_user.username if bot_user else ""
        
        is_mention = False
        if isinstance(event, Message):
            text_lower = event.text.lower()
            if bot_username and f"@{bot_username.lower()}" in text_lower:
                is_mention = True
            elif text_lower.startswith("бот,") or text_lower.startswith("бот ") or text_lower == "бот":
                is_mention = True
            elif event.reply_to_message and event.reply_to_message.from_user and bot_user and event.reply_to_message.from_user.id == bot_user.id:
                is_mention = True
                
        if is_mention and not trigger:
            trigger = "mention"

        data["message_buffer"] = self._buffer
        data["trigger_type"] = trigger
        data["should_analyze"] = (
            trigger is not None
            or self._buffer.should_analyze(
                event.chat.id,
                self._settings.message_threshold,
                0,  # cooldown checked in rate_limit middleware
            )
        )

        return await handler(event, data)
