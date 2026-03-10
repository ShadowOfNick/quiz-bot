import json
import logging
from dataclasses import dataclass

from app.llm.base import LLMProvider
from app.llm.prompts import CLASSIFY_MESSAGES
from app.utils.message_buffer import BufferedMessage
from app.utils.text_utils import format_messages_for_llm, parse_json_from_llm

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    should_respond: bool
    response_type: str  # "meetup", "reminder", "question", "none"
    confidence: float
    summary: str
    suggested_action: str
    suggested_response: str


class AIAnalyzer:
    def __init__(self, llm: LLMProvider, confidence_threshold: float = 0.7):
        self._llm = llm
        self._confidence_threshold = confidence_threshold

    async def analyze_messages(
        self, messages: list[BufferedMessage]
    ) -> AnalysisResult | None:
        if not messages:
            return None

        formatted = format_messages_for_llm(
            [{"username": m.username, "text": m.text} for m in messages]
        )
        prompt = CLASSIFY_MESSAGES.format(messages=formatted)

        try:
            response = await self._llm.complete(
                messages=[
                    {"role": "system", "content": "Ты — аналитик группового чата."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=400,
                temperature=0.3,
            )

            data = parse_json_from_llm(response.content)
            if not data:
                return None

            result = AnalysisResult(
                should_respond=data.get("should_respond", False),
                response_type=data.get("response_type", "none"),
                confidence=data.get("confidence", 0.0),
                summary=data.get("summary", ""),
                suggested_action=data.get("suggested_action", ""),
                suggested_response=data.get("suggested_response", ""),
            )

            if result.confidence < self._confidence_threshold:
                result.should_respond = False

            return result

        except (json.JSONDecodeError, KeyError):
            logger.exception("Failed to parse AI response")
            return None
        except Exception:
            logger.exception("AI analysis failed")
            return None

    async def generate_direct_response(
        self, messages: list[BufferedMessage]
    ) -> str | None:
        if not messages:
            return None

        from app.llm.prompts import DIRECT_RESPONSE
        formatted = format_messages_for_llm(
            [{"username": m.username, "text": m.text} for m in messages]
        )
        prompt = DIRECT_RESPONSE.format(messages=formatted)

        try:
            response = await self._llm.complete(
                messages=[
                    {"role": "system", "content": "Ты — разговорчивый бот-помощник в групповом чате."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=300,
                temperature=0.8,
            )
            return response.content.strip()
        except Exception:
            logger.exception("Direct response generation failed")
            return None
