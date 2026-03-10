from datetime import datetime

import asyncpg

from app.db.models import Reminder


class ReminderRepository:
    def __init__(self, conn: asyncpg.Connection):
        self._conn = conn

    async def save(self, reminder: Reminder) -> None:
        await self._conn.execute(
            """INSERT INTO reminders
               (chat_id, user_id, reminder_text, remind_at, created_at, is_fired)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            reminder.chat_id,
            reminder.user_id,
            reminder.reminder_text,
            reminder.remind_at,
            reminder.created_at,
            reminder.is_fired,
        )

    async def get_due(self) -> list[Reminder]:
        now = datetime.now()
        rows = await self._conn.fetch(
            """SELECT * FROM reminders
               WHERE is_fired = FALSE AND remind_at <= $1
               ORDER BY remind_at ASC""",
            now,
        )
        return [self._row_to_reminder(r) for r in rows]

    async def mark_fired(self, reminder_id: int) -> None:
        await self._conn.execute(
            "UPDATE reminders SET is_fired = TRUE WHERE id = $1",
            reminder_id,
        )

    @staticmethod
    def _row_to_reminder(row: asyncpg.Record) -> Reminder:
        return Reminder(
            id=row["id"],
            chat_id=row["chat_id"],
            user_id=row["user_id"],
            reminder_text=row["reminder_text"],
            remind_at=row["remind_at"],
            created_at=row["created_at"],
            is_fired=bool(row["is_fired"]),
        )
