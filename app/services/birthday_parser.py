import logging
from dataclasses import dataclass
from datetime import datetime, date

from app.llm.base import LLMProvider
from app.llm.prompts import PARSE_BIRTHDAY_MENTION
from app.utils.text_utils import parse_json_from_llm

logger = logging.getLogger(__name__)


@dataclass
class BirthdayMention:
    has_birthday: bool
    is_author: bool  # True if "my birthday", False if mentions someone else
    mentioned_username: str | None
    birth_date: date | None
    confidence: float


class BirthdayParser:
    def __init__(self, llm: LLMProvider):
        self._llm = llm

    async def parse_birthday_mention(
        self, text: str
    ) -> BirthdayMention | None:
        """Parse message for birthday mentions."""
        now = datetime.now()
        prompt = PARSE_BIRTHDAY_MENTION.format(
            message=text,
            now=now.strftime("%Y-%m-%d"),
        )

        try:
            response = await self._llm.complete(
                messages=[
                    {
                        "role": "system",
                        "content": "Ты парсишь упоминания дней рождения из сообщений. Отвечай только JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=200,
                temperature=0.2,
            )
            data = parse_json_from_llm(response.content)

            if not data or not data.get("has_birthday", False):
                return None

            # Parse birth date
            birth_date = None
            if data.get("birth_date"):
                try:
                    birth_date = datetime.fromisoformat(data["birth_date"]).date()
                except (ValueError, TypeError):
                    logger.warning("Failed to parse birth_date: %s", data.get("birth_date"))
                    return None

            if data.get("confidence", 0.0) < 0.6:
                return None

            return BirthdayMention(
                has_birthday=True,
                is_author=data.get("is_author", True),
                mentioned_username=data.get("mentioned_username"),
                birth_date=birth_date,
                confidence=data.get("confidence", 0.0),
            )

        except Exception:
            logger.exception("Birthday mention parsing failed")
            return None
