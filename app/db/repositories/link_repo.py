import asyncpg

from app.db.models import Link


class LinkRepository:
    def __init__(self, conn: asyncpg.Connection):
        self._conn = conn

    async def save(self, link: Link) -> None:
        await self._conn.execute(
            """INSERT INTO links (chat_id, user_id, url, title, context, created_at)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            link.chat_id,
            link.user_id,
            link.url,
            link.title,
            link.context,
            link.created_at,
        )

    async def get_recent(
        self, chat_id: int, limit: int = 20
    ) -> list[Link]:
        rows = await self._conn.fetch(
            """SELECT * FROM links WHERE chat_id = $1
               ORDER BY created_at DESC LIMIT $2""",
            chat_id,
            limit,
        )
        return [
            Link(
                id=r["id"],
                chat_id=r["chat_id"],
                user_id=r["user_id"],
                url=r["url"],
                title=r["title"],
                context=r["context"],
                created_at=r["created_at"],
            )
            for r in rows
        ]
