from datetime import date

import asyncpg


class StatsRepository:
    def __init__(self, conn: asyncpg.Connection):
        self._conn = conn

    async def increment_proactive(self, chat_id: int) -> int:
        today = date.today()
        await self._conn.execute(
            """INSERT INTO bot_daily_stats (chat_id, date, proactive_messages_sent)
               VALUES ($1, $2, 1)
               ON CONFLICT(chat_id, date) DO UPDATE SET
                 proactive_messages_sent = bot_daily_stats.proactive_messages_sent + 1""",
            chat_id,
            today,
        )
        row = await self._conn.fetchrow(
            """SELECT proactive_messages_sent FROM bot_daily_stats
               WHERE chat_id = $1 AND date = $2""",
            chat_id,
            today,
        )
        return row["proactive_messages_sent"] if row else 1

    async def increment_commands(self, chat_id: int) -> None:
        today = date.today()
        await self._conn.execute(
            """INSERT INTO bot_daily_stats (chat_id, date, commands_handled)
               VALUES ($1, $2, 1)
               ON CONFLICT(chat_id, date) DO UPDATE SET
                 commands_handled = bot_daily_stats.commands_handled + 1""",
            chat_id,
            today,
        )

    async def get_daily_proactive_count(self, chat_id: int) -> int:
        today = date.today()
        row = await self._conn.fetchrow(
            """SELECT proactive_messages_sent FROM bot_daily_stats
               WHERE chat_id = $1 AND date = $2""",
            chat_id,
            today,
        )
        return row["proactive_messages_sent"] if row else 0

    async def get_message_stats(self, chat_id: int, days: int = 7) -> list[dict]:
        rows = await self._conn.fetch(
            """SELECT user_id, username, display_name,
                      COUNT(*) as message_count,
                      SUM(LENGTH(text)) as total_chars
               FROM messages
               WHERE chat_id = $1
                 AND created_at >= NOW() - INTERVAL '$2 days'
               GROUP BY user_id, username, display_name
               ORDER BY message_count DESC
               LIMIT 15""",
            chat_id,
            days,
        )
        return [
            {
                "user_id": r["user_id"],
                "username": r["username"],
                "display_name": r["display_name"],
                "message_count": r["message_count"],
                "total_chars": r["total_chars"],
            }
            for r in rows
        ]
