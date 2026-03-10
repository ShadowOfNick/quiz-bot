import logging
from datetime import date

from app.db.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


class BirthdayService:
    async def check_todays_birthdays(
        self, repo: UserRepository
    ) -> list[dict]:
        today = date.today()
        users = await repo.get_birthdays_on(today.month, today.day)
        return [
            {
                "user_id": u.user_id,
                "username": u.username,
                "display_name": u.display_name,
            }
            for u in users
        ]

    @staticmethod
    def format_birthday_message(birthdays: list[dict]) -> str:
        if not birthdays:
            return ""
        lines = ["🎂 <b>Сегодня день рождения:</b>"]
        for b in birthdays:
            name = b["display_name"] or b["username"] or f"user_{b['user_id']}"
            if b["username"]:
                lines.append(f"  🎉 @{b['username']} ({name})")
            else:
                lines.append(f"  🎉 {name}")
        lines.append("\nПоздравляем! 🥳")
        return "\n".join(lines)
