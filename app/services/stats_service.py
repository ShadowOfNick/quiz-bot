from app.db.repositories.stats_repo import StatsRepository


class StatsService:
    async def format_stats(
        self, chat_id: int, repo: StatsRepository, days: int = 7
    ) -> str:
        stats = await repo.get_message_stats(chat_id, days)
        if not stats:
            return f"Нет статистики за последние {days} дней."

        total = sum(s["message_count"] for s in stats)
        lines = [f"📊 <b>Статистика за {days} дней</b>", f"Всего сообщений: {total}\n"]

        medals = ["🥇", "🥈", "🥉"]
        for i, s in enumerate(stats[:10]):
            name = s["display_name"] or s["username"] or f"user_{s['user_id']}"
            medal = medals[i] if i < 3 else f"{i + 1}."
            avg_len = s["total_chars"] // s["message_count"] if s["message_count"] else 0
            lines.append(
                f"{medal} {name} — {s['message_count']} сообщений "
                f"(~{avg_len} символов/сообщ.)"
            )

        return "\n".join(lines)
