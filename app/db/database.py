import logging
from typing import Union

import asyncpg

logger = logging.getLogger(__name__)

# PostgreSQL schema
POSTGRES_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS messages (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    username TEXT,
    display_name TEXT,
    text TEXT,
    message_id BIGINT NOT NULL,
    reply_to_message_id BIGINT,
    has_links BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_messages_chat_time ON messages(chat_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, chat_id);

CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username TEXT,
    display_name TEXT,
    birthday DATE,
    first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quiz_scores (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    points INTEGER NOT NULL DEFAULT 0,
    is_correct BOOLEAN NOT NULL,
    quiz_question TEXT,
    answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_quiz_scores_user_chat ON quiz_scores(user_id, chat_id);

CREATE TABLE IF NOT EXISTS links (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    url TEXT NOT NULL,
    title TEXT,
    context TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_links_chat ON links(chat_id, created_at);

CREATE TABLE IF NOT EXISTS reminders (
    id SERIAL PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    reminder_text TEXT NOT NULL,
    remind_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_fired BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_reminders_fire ON reminders(remind_at, is_fired);

CREATE TABLE IF NOT EXISTS bot_daily_stats (
    chat_id BIGINT NOT NULL,
    date DATE NOT NULL,
    proactive_messages_sent INTEGER DEFAULT 0,
    commands_handled INTEGER DEFAULT 0,
    ai_calls_made INTEGER DEFAULT 0,
    PRIMARY KEY (chat_id, date)
);
"""


class Database:
    """
    Класс для работы с базой данных.
    Поддерживает PostgreSQL через asyncpg.
    """

    def __init__(self, db_url: str):
        """
        Args:
            db_url: URL подключения к PostgreSQL
        """
        self._db_url = db_url
        self._pool: Union[asyncpg.Pool, None] = None

    async def initialize(self) -> None:
        """Инициализация пула соединений и создание таблиц"""
        self._pool = await asyncpg.create_pool(
            self._db_url,
            min_size=2,
            max_size=10,
            command_timeout=60,
        )
        logger.info("Database pool created")

        # Создаём таблицы
        async with self._pool.acquire() as conn:
            await conn.execute(POSTGRES_SCHEMA_SQL)
        logger.info("Database schema initialized")

    @property
    def pool(self) -> asyncpg.Pool:
        """Возвращает пул соединений"""
        if self._pool is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return self._pool

    async def acquire(self) -> asyncpg.Connection:
        """Получает соединение из пула"""
        return await self.pool.acquire()

    async def release(self, connection: asyncpg.Connection) -> None:
        """Возвращает соединение в пул"""
        await self.pool.release(connection)

    async def close(self) -> None:
        """Закрывает пул соединений"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("Database pool closed")
