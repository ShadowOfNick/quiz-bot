from datetime import date, datetime

import aiosqlite

from app.db.models import User


class UserRepository:
    def __init__(self, conn: aiosqlite.Connection):
        self._conn = conn

    async def upsert(self, user: User) -> None:
        await self._conn.execute(
            """INSERT INTO users (user_id, username, display_name, first_seen_at, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                 username = excluded.username,
                 display_name = excluded.display_name,
                 updated_at = excluded.updated_at""",
            (
                user.user_id,
                user.username,
                user.display_name,
                user.first_seen_at.isoformat(),
                datetime.now().isoformat(),
            ),
        )
        await self._conn.commit()

    async def set_birthday(self, user_id: int, birthday: date) -> None:
        await self._conn.execute(
            "UPDATE users SET birthday = ? WHERE user_id = ?",
            (birthday.isoformat(), user_id),
        )
        await self._conn.commit()

    async def get_birthdays_on(self, month: int, day: int) -> list[User]:
        cursor = await self._conn.execute(
            """SELECT * FROM users
               WHERE birthday IS NOT NULL
               AND CAST(strftime('%%m', birthday) AS INTEGER) = ?
               AND CAST(strftime('%%d', birthday) AS INTEGER) = ?""",
            (month, day),
        )
        rows = await cursor.fetchall()
        return [self._row_to_user(r) for r in rows]

    async def get_upcoming_birthdays(self, days_ahead: int) -> list[User]:
        """Get users with birthdays in N days from now."""
        from datetime import timedelta

        target_date = date.today() + timedelta(days=days_ahead)
        month = target_date.month
        day = target_date.day

        return await self.get_birthdays_on(month, day)

    async def get(self, user_id: int) -> User | None:
        cursor = await self._conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return self._row_to_user(row) if row else None

    @staticmethod
    def _row_to_user(row: aiosqlite.Row) -> User:
        bday = row["birthday"]
        return User(
            user_id=row["user_id"],
            username=row["username"],
            display_name=row["display_name"],
            birthday=date.fromisoformat(bday) if bday else None,
            first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
        )
