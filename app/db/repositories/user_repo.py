from datetime import date, datetime

import asyncpg

from app.db.models import User


class UserRepository:
    def __init__(self, conn: asyncpg.Connection):
        self._conn = conn

    async def upsert(self, user: User) -> None:
        await self._conn.execute(
            """INSERT INTO users (user_id, username, display_name, first_seen_at, updated_at)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT(user_id) DO UPDATE SET
                 username = excluded.username,
                 display_name = excluded.display_name,
                 updated_at = excluded.updated_at""",
            user.user_id,
            user.username,
            user.display_name,
            user.first_seen_at,
            datetime.now(),
        )

    async def set_birthday(self, user_id: int, birthday: date) -> None:
        await self._conn.execute(
            "UPDATE users SET birthday = $1 WHERE user_id = $2",
            birthday,
            user_id,
        )

    async def get_birthdays_on(self, month: int, day: int) -> list[User]:
        rows = await self._conn.fetch(
            """SELECT * FROM users
               WHERE birthday IS NOT NULL
               AND EXTRACT(MONTH FROM birthday) = $1
               AND EXTRACT(DAY FROM birthday) = $2""",
            month,
            day,
        )
        return [self._row_to_user(r) for r in rows]

    async def get_upcoming_birthdays(self, days_ahead: int) -> list[User]:
        """Get users with birthdays in N days from now."""
        from datetime import timedelta

        target_date = date.today() + timedelta(days=days_ahead)
        month = target_date.month
        day = target_date.day

        return await self.get_birthdays_on(month, day)

    async def get(self, user_id: int) -> User | None:
        row = await self._conn.fetchrow(
            "SELECT * FROM users WHERE user_id = $1", user_id
        )
        return self._row_to_user(row) if row else None

    @staticmethod
    def _row_to_user(row: asyncpg.Record) -> User:
        bday = row["birthday"]
        return User(
            user_id=row["user_id"],
            username=row["username"],
            display_name=row["display_name"],
            birthday=bday if isinstance(bday, date) else (date.fromisoformat(bday) if bday else None),
            first_seen_at=row["first_seen_at"] if isinstance(row["first_seen_at"], datetime) else datetime.fromisoformat(row["first_seen_at"]),
        )
