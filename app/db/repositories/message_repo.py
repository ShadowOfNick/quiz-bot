from datetime import datetime

import asyncpg

from app.db.models import Message


class MessageRepository:
    def __init__(self, conn: asyncpg.Connection):
        self._conn = conn

    async def save(self, msg: Message) -> None:
        await self._conn.execute(
            """INSERT INTO messages (chat_id, user_id, username, display_name,
               text, message_id, reply_to_message_id, has_links, created_at)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
            msg.chat_id,
            msg.user_id,
            msg.username,
            msg.display_name,
            msg.text,
            msg.message_id,
            msg.reply_to_message_id,
            msg.has_links,
            msg.created_at,
        )

    async def get_recent(
        self, chat_id: int, limit: int = 50
    ) -> list[Message]:
        rows = await self._conn.fetch(
            """SELECT * FROM messages WHERE chat_id = $1
               ORDER BY created_at DESC LIMIT $2""",
            chat_id,
            limit,
        )
        return [self._row_to_message(r) for r in reversed(rows)]

    async def get_since(
        self, chat_id: int, since: datetime
    ) -> list[Message]:
        rows = await self._conn.fetch(
            """SELECT * FROM messages WHERE chat_id = $1 AND created_at >= $2
               ORDER BY created_at ASC""",
            chat_id,
            since,
        )
        return [self._row_to_message(r) for r in rows]

    async def cleanup_old(self, days: int) -> int:
        result = await self._conn.execute(
            """DELETE FROM messages
               WHERE created_at < NOW() - INTERVAL '$1 days'""",
            days,
        )
        # result будет строкой вида "DELETE 5"
        return int(result.split()[-1]) if result else 0

    @staticmethod
    def _row_to_message(row: asyncpg.Record) -> Message:
        return Message(
            id=row["id"],
            chat_id=row["chat_id"],
            user_id=row["user_id"],
            username=row["username"],
            display_name=row["display_name"],
            text=row["text"] or "",
            message_id=row["message_id"],
            reply_to_message_id=row["reply_to_message_id"],
            has_links=bool(row["has_links"]),
            created_at=row["created_at"],
        )
