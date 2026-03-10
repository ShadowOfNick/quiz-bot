import logging
from datetime import datetime
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from app.config import RateLimitSettings
from app.utils.message_buffer import MessageBuffer
from app.utils.rate_limiter import TokenBucketRateLimiter

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, settings: RateLimitSettings, buffer: MessageBuffer):
        self._settings = settings
        self._buffer = buffer
        self._bucket = TokenBucketRateLimiter(
            rate=settings.bucket_rate,
            capacity=settings.bucket_capacity,
        )
        self._last_command_time: dict[int, datetime] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, Message) or not event.text:
            return await handler(event, data)

        chat_id = event.chat.id
        is_command = event.text.startswith("/")

        if is_command:
            # Light rate limit for commands
            last = self._last_command_time.get(chat_id)
            if last:
                elapsed = (datetime.now() - last).total_seconds()
                if elapsed < self._settings.command_cooldown_seconds:
                    return  # silently skip
            data["rate_limited"] = False
        else:
            # For proactive responses: check cooldown + token bucket
            should_analyze = data.get("should_analyze", False)
            trigger_type = data.get("trigger_type")

            if should_analyze and not trigger_type:
                # Check cooldown only if it's NOT a direct trigger
                last_response = self._buffer._last_bot_response_time.get(chat_id)
                if last_response:
                    elapsed = (datetime.now() - last_response).total_seconds()
                    if elapsed < self._settings.proactive_cooldown_seconds:
                        data["should_analyze"] = False
                        data["rate_limited"] = True
                        return await handler(event, data)

                # Check token bucket
                if not self._bucket.try_consume(chat_id):
                    data["should_analyze"] = False
                    data["rate_limited"] = True
                    return await handler(event, data)

            data["rate_limited"] = False

        data["rate_limit_middleware"] = self

        return await handler(event, data)

    def record_command(self, chat_id: int) -> None:
        self._last_command_time[chat_id] = datetime.now()
