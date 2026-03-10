from pydantic import BaseModel
from pydantic_settings import BaseSettings


class BotSettings(BaseModel):
    token: str = ""
    admin_ids: list[int] = []


class LLMSettings(BaseModel):
    provider: str = "gemma"
    gemma_api_key: str = ""
    gemma_model: str = "gemma-3-27b-it"
    max_tokens: int = 500
    temperature: float = 0.7


class AnalysisSettings(BaseModel):
    message_threshold: int = 10
    confidence_threshold: float = 0.7
    buffer_size: int = 100


class RateLimitSettings(BaseModel):
    proactive_cooldown_seconds: int = 120
    bucket_rate: float = 0.008
    bucket_capacity: int = 5
    daily_proactive_cap: int = 20
    command_cooldown_seconds: int = 5


class QuizSettings(BaseModel):
    inactivity_threshold_minutes: int = 120
    question_timeout_seconds: int = 30
    points_first: int = 3
    points_second: int = 2
    points_third: int = 1


class DatabaseSettings(BaseModel):
    url: str = ""
    path: str = "data/bot.db"
    message_retention_days: int = 7

    @property
    def is_postgres(self) -> bool:
        """Проверка, используется ли PostgreSQL"""
        return self.url.startswith("postgres://") or self.url.startswith("postgresql://")


class Settings(BaseSettings):
    bot: BotSettings = BotSettings()
    llm: LLMSettings = LLMSettings()
    analysis: AnalysisSettings = AnalysisSettings()
    rate_limit: RateLimitSettings = RateLimitSettings()
    quiz: QuizSettings = QuizSettings()
    db: DatabaseSettings = DatabaseSettings()

    model_config = {"env_file": ".env", "env_nested_delimiter": "__"}
