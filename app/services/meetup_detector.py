import json
import logging

from app.llm.base import LLMProvider
from app.llm.prompts import MEETUP_RESPONSE
from app.utils.message_buffer import BufferedMessage
from app.utils.text_utils import format_messages_for_llm

logger = logging.getLogger(__name__)


class MeetupDetector:
    def __init__(self, llm: LLMProvider):
        self._llm = llm

    async def generate_meetup_response(
        self, messages: list[BufferedMessage]
    ) -> str | None:
        formatted = format_messages_for_llm(
            [{"username": m.username, "text": m.text} for m in messages]
        )
        prompt = MEETUP_RESPONSE.format(messages=formatted)

        try:
            response = await self._llm.complete(
                messages=[
                    {
                        "role": "system",
                        "content": "Ты — дружелюбный бот-помощник в групповом чате.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=300,
                temperature=0.7,
            )
            return response.content.strip() or "Вижу вы обсуждаете встречу! Может, сделать опрос, чтобы выбрать время?"
        except Exception:
            logger.exception("Meetup response generation failed")
            return "Вижу вы обсуждаете встречу! В какой день вам удобнее?"

    async def is_same_event(self, prev_context: str, current_text: str) -> bool:
        """Check if current message is about the same event as previous context."""
        prompt = f"""Сравни два упоминания встречи/события и определи, о ОДНОМ И ТОМ ЖЕ событии речь или о РАЗНЫХ.

Предыдущий контекст: "{prev_context}"
Текущее сообщение: "{current_text}"

Примеры ОДНОГО события:
- "Кто хочет на квиз 20 марта?" и "Кто еще пойдет?" - ТО ЖЕ
- "Встречаемся завтра" и "Во сколько завтра?" - ТО ЖЕ

Примеры РАЗНЫХ событий:
- "Кто хочет на квиз 20 марта?" и "Кто хочет на квиз 13 марта?" - РАЗНЫЕ (разные даты)
- "Встречаемся в кафе" и "Кто пойдет в кино?" - РАЗНЫЕ (разные места/активности)

Ответь строго в формате JSON:
{{
  "is_same": true/false
}}"""

        try:
            response = await self._llm.complete(
                messages=[
                    {"role": "system", "content": "Ты анализируешь, о том же событии речь или о разных."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=50,
                temperature=0.2,
            )

            from app.utils.text_utils import parse_json_from_llm
            data = parse_json_from_llm(response.content)
            if data and "is_same" in data:
                return data["is_same"]
        except Exception:
            logger.exception("Failed to compare meetup contexts")

        # If unsure, assume it's the same to avoid spam
        return True

    async def generate_poll_options(
        self, messages: list[BufferedMessage]
    ) -> dict:
        """Generate poll options based on message context."""
        formatted = format_messages_for_llm(
            [{"username": m.username, "text": m.text} for m in messages]
        )

        prompt = f"""Проанализируй обсуждение встречи и создай опрос.
Если в сообщениях упоминается конкретная дата/время/место - используй их в вариантах.

Сообщения:
{formatted}

Ответь строго в формате JSON:
{{
  "question": "вопрос для опроса (например: 'Кто пойдет на квиз 20 марта?')",
  "options": ["вариант 1", "вариант 2", "вариант 3", "вариант 4", "вариант 5"]
}}

Если упоминается конкретное событие (квиз, встреча и т.д.) и дата - сделай вопрос конкретным.
Варианты должны быть релевантны контексту (например: "Да, буду", "Нет", "Может быть", "Не уверен", "Зависит от времени")."""

        try:
            response = await self._llm.complete(
                messages=[
                    {"role": "system", "content": "Ты создаешь опросы для групповых встреч."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=300,
                temperature=0.5,
            )

            from app.utils.text_utils import parse_json_from_llm
            data = parse_json_from_llm(response.content)

            if data and "question" in data and "options" in data:
                return {
                    "question": data["question"],
                    "options": data["options"][:5],  # Max 5 options
                }
        except Exception:
            logger.exception("Failed to generate poll options from context")

        # Fallback to default options
        return {
            "question": "Когда удобно встретиться?",
            "options": [
                "Сегодня вечером",
                "Завтра",
                "В эти выходные",
                "На следующей неделе",
                "Не смогу",
            ],
        }
