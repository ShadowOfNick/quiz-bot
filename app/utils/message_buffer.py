import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class BufferedMessage:
    chat_id: int
    user_id: int
    username: str
    text: str
    timestamp: datetime
    message_id: int


class MessageBuffer:
    """Per-chat ring buffer for recent messages with analysis tracking."""

    def __init__(self, max_size: int = 100):
        self._buffers: dict[int, deque[BufferedMessage]] = {}
        self._messages_since_analysis: dict[int, int] = {}
        self._last_analysis_time: dict[int, datetime] = {}
        self._last_bot_response_time: dict[int, datetime] = {}
        self._last_meetup_context: dict[int, str] = {}  # Store last meetup message context
        self._cooldown_tasks: dict[int, asyncio.Task[Any]] = {}  # Track active cooldown notification tasks
        self._max_size = max_size

    def add(self, msg: BufferedMessage) -> None:
        chat_id = msg.chat_id
        if chat_id not in self._buffers:
            self._buffers[chat_id] = deque(maxlen=self._max_size)
            self._messages_since_analysis[chat_id] = 0
        self._buffers[chat_id].append(msg)
        self._messages_since_analysis[chat_id] += 1

    def get_recent(self, chat_id: int, n: int = 20) -> list[BufferedMessage]:
        buf = self._buffers.get(chat_id)
        if not buf:
            return []
        items = list(buf)
        return items[-n:]

    def get_since_last_analysis(self, chat_id: int) -> list[BufferedMessage]:
        buf = self._buffers.get(chat_id)
        if not buf:
            return []
        last_time = self._last_analysis_time.get(chat_id)
        if last_time is None:
            return list(buf)
        return [m for m in buf if m.timestamp > last_time]

    def mark_analyzed(self, chat_id: int) -> None:
        self._messages_since_analysis[chat_id] = 0
        self._last_analysis_time[chat_id] = datetime.now()

    def mark_bot_responded(self, chat_id: int) -> None:
        self._last_bot_response_time[chat_id] = datetime.now()

    def should_analyze(
        self, chat_id: int, threshold: int, cooldown_seconds: int
    ) -> bool:
        count = self._messages_since_analysis.get(chat_id, 0)
        if count < threshold:
            return False
        last_response = self._last_bot_response_time.get(chat_id)
        if last_response:
            elapsed = (datetime.now() - last_response).total_seconds()
            if elapsed < cooldown_seconds:
                return False
        return True

    def get_last_message_time(self, chat_id: int) -> datetime | None:
        buf = self._buffers.get(chat_id)
        if not buf:
            return None
        return buf[-1].timestamp

    def get_messages_since_analysis_count(self, chat_id: int) -> int:
        return self._messages_since_analysis.get(chat_id, 0)

    def get_active_chat_ids(self) -> list[int]:
        return list(self._buffers.keys())

    def was_bot_active_recently(self, chat_id: int, seconds: int = 300) -> bool:
        """Check if bot responded in the last N seconds (default 5 minutes)."""
        last_response = self._last_bot_response_time.get(chat_id)
        if not last_response:
            return False
        elapsed = (datetime.now() - last_response).total_seconds()
        return elapsed < seconds

    def get_cooldown_remaining(self, chat_id: int, cooldown_seconds: int) -> int:
        """Get remaining cooldown time in seconds. Returns 0 if no cooldown."""
        last_response = self._last_bot_response_time.get(chat_id)
        if not last_response:
            return 0
        elapsed = (datetime.now() - last_response).total_seconds()
        remaining = max(0, cooldown_seconds - elapsed)
        return int(remaining)

    def set_last_meetup_context(self, chat_id: int, context: str) -> None:
        """Store the context of the last meetup trigger."""
        self._last_meetup_context[chat_id] = context

    def get_last_meetup_context(self, chat_id: int) -> str | None:
        """Get the context of the last meetup trigger."""
        return self._last_meetup_context.get(chat_id)

    def has_active_cooldown_task(self, chat_id: int) -> bool:
        """Check if there's an active cooldown notification task for this chat."""
        task = self._cooldown_tasks.get(chat_id)
        return task is not None and not task.done()

    def set_cooldown_task(self, chat_id: int, task: asyncio.Task[Any]) -> None:
        """Store a cooldown notification task for this chat."""
        # Cancel any existing task first
        if chat_id in self._cooldown_tasks:
            old_task = self._cooldown_tasks[chat_id]
            if not old_task.done():
                old_task.cancel()
        self._cooldown_tasks[chat_id] = task

    def clear_cooldown_task(self, chat_id: int) -> None:
        """Clear the cooldown notification task for this chat."""
        if chat_id in self._cooldown_tasks:
            del self._cooldown_tasks[chat_id]
