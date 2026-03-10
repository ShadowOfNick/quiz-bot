import json
import logging
from datetime import datetime

from app.db.models import Reminder
from app.db.repositories.reminder_repo import ReminderRepository
from app.llm.base import LLMProvider
from app.llm.prompts import PARSE_REMINDER
from app.utils.text_utils import parse_json_from_llm

logger = logging.getLogger(__name__)


class ReminderService:
    def __init__(self, llm: LLMProvider):
        self._llm = llm

    async def parse_and_save(
        self,
        text: str,
        chat_id: int,
        user_id: int,
        repo: ReminderRepository,
    ) -> Reminder | None:
        now = datetime.now()
        prompt = PARSE_REMINDER.format(message=text, now=now.isoformat())

        try:
            response = await self._llm.complete(
                messages=[
                    {
                        "role": "system",
                        "content": "Ты парсишь напоминания из сообщений. Отвечай только JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=200,
                temperature=0.2,
            )
            data = parse_json_from_llm(response.content)

            if not data or not data.get("is_valid", False):
                return None

            remind_at = datetime.fromisoformat(data["remind_at"])
            if remind_at <= now:
                return None

            reminder = Reminder(
                chat_id=chat_id,
                user_id=user_id,
                reminder_text=data["reminder_text"],
                remind_at=remind_at,
            )
            await repo.save(reminder)
            return reminder

        except (KeyError, ValueError):
            logger.exception("Failed to parse reminder")
            return None
        except Exception:
            logger.exception("Reminder parsing failed")
            return None
