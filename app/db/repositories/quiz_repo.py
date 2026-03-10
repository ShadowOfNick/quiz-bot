from datetime import datetime

import asyncpg

from app.db.models import QuizScore


class QuizRepository:
    def __init__(self, conn: asyncpg.Connection):
        self._conn = conn

    async def save_score(self, score: QuizScore) -> None:
        await self._conn.execute(
            """INSERT INTO quiz_scores
               (chat_id, user_id, points, is_correct, quiz_question, answered_at)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            score.chat_id,
            score.user_id,
            score.points,
            score.is_correct,
            score.quiz_question,
            score.answered_at,
        )

    async def get_leaderboard(
        self, chat_id: int, limit: int = 10
    ) -> list[dict]:
        rows = await self._conn.fetch(
            """SELECT user_id,
                      SUM(points) as total_points,
                      COUNT(*) as quizzes_played,
                      SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct_answers
               FROM quiz_scores
               WHERE chat_id = $1
               GROUP BY user_id
               ORDER BY total_points DESC
               LIMIT $2""",
            chat_id,
            limit,
        )
        return [
            {
                "user_id": r["user_id"],
                "total_points": r["total_points"],
                "quizzes_played": r["quizzes_played"],
                "correct_answers": r["correct_answers"],
            }
            for r in rows
        ]
