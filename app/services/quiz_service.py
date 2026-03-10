import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from app.db.models import QuizScore
from app.db.repositories.quiz_repo import QuizRepository
from app.llm.base import LLMProvider
from app.llm.prompts import GENERATE_QUIZ
from app.utils.text_utils import parse_json_from_llm

logger = logging.getLogger(__name__)


@dataclass
class QuizSession:
    id: str
    chat_id: int
    question: str
    options: list[str]
    correct_index: int
    explanation: str
    created_at: datetime = field(default_factory=datetime.now)
    answers: dict[int, int] = field(default_factory=dict)  # user_id -> chosen_index
    finished: bool = False

    @property
    def correct_count(self) -> int:
        return sum(1 for idx in self.answers.values() if idx == self.correct_index)

    def get_results_text(self, usernames: dict[int, str]) -> str:
        if not self.answers:
            return "Никто не ответил на квиз."

        lines = [f"<b>Правильный ответ:</b> {self.options[self.correct_index]}"]
        lines.append(f"<i>{self.explanation}</i>\n")

        correct_users = []
        wrong_users = []
        for uid, idx in self.answers.items():
            name = usernames.get(uid, f"user_{uid}")
            if idx == self.correct_index:
                correct_users.append(name)
            else:
                wrong_users.append(name)

        if correct_users:
            lines.append(f"Правильно ответили: {', '.join(correct_users)}")
        if wrong_users:
            lines.append(f"Ошиблись: {', '.join(wrong_users)}")

        return "\n".join(lines)


class QuizService:
    def __init__(self, llm: LLMProvider):
        self._llm = llm
        self._active_sessions: dict[int, QuizSession] = {}  # chat_id -> session

    def get_active_session(self, chat_id: int) -> QuizSession | None:
        session = self._active_sessions.get(chat_id)
        if session and not session.finished:
            return session
        return None

    async def create_quiz(
        self, chat_id: int, context: str = ""
    ) -> QuizSession | None:
        context_text = (
            f"Контекст недавнего обсуждения в чате:\n{context}"
            if context
            else "Без контекста, выбери интересную общую тему."
        )
        prompt = GENERATE_QUIZ.format(context=context_text)

        try:
            response = await self._llm.complete(
                messages=[
                    {
                        "role": "system",
                        "content": "Ты генерируешь вопросы для квизов. Отвечай только JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=400,
                temperature=0.9,
            )
            data = parse_json_from_llm(response.content)
            if not data:
                return None
                
            session = QuizSession(
                id=str(uuid.uuid4()),
                chat_id=chat_id,
                question=data["question"],
                options=data["options"],
                correct_index=data["correct_index"],
                explanation=data.get("explanation", ""),
            )
            self._active_sessions[chat_id] = session
            return session

        except KeyError:
            logger.exception("Failed to parse quiz response")
            return None
        except Exception:
            logger.exception("Quiz generation failed")
            return None

    def record_answer(
        self, chat_id: int, user_id: int, answer_index: int
    ) -> bool:
        """Record answer. Returns True if this is a new answer."""
        session = self.get_active_session(chat_id)
        if not session or user_id in session.answers:
            return False
        session.answers[user_id] = answer_index
        return True

    def finish_quiz(self, chat_id: int) -> QuizSession | None:
        session = self._active_sessions.get(chat_id)
        if session:
            session.finished = True
        return session

    async def save_scores(
        self, session: QuizSession, quiz_repo: QuizRepository
    ) -> None:
        correct_order = [
            uid
            for uid, idx in session.answers.items()
            if idx == session.correct_index
        ]

        for i, uid in enumerate(session.answers):
            chosen = session.answers[uid]
            is_correct = chosen == session.correct_index
            if is_correct:
                rank = correct_order.index(uid)
                points = max(1, 3 - rank)  # 3, 2, 1, 1, 1...
            else:
                points = 0

            score = QuizScore(
                chat_id=session.chat_id,
                user_id=uid,
                points=points,
                is_correct=is_correct,
                quiz_question=session.question,
            )
            await quiz_repo.save_score(score)
