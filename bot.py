import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import Settings
from app.db.database import Database
from app.handlers import register_all_handlers
from app.llm import create_llm_provider
from app.middlewares.db_session import DbSessionMiddleware
from app.middlewares.message_collector import MessageCollectorMiddleware
from app.middlewares.rate_limit import RateLimitMiddleware
from app.scheduler.jobs import register_jobs
from app.services.ai_analyzer import AIAnalyzer
from app.services.birthday_parser import BirthdayParser
from app.services.link_collector import LinkCollector
from app.services.meetup_detector import MeetupDetector
from app.services.quiz_service import QuizService
from app.services.reminder_service import ReminderService
from app.services.stats_service import StatsService
from app.utils.message_buffer import MessageBuffer


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    settings = Settings()

    # Database
    db = Database(settings.db.url)
    await db.initialize()

    # LLM
    llm = create_llm_provider(settings.llm)

    # Core components
    buffer = MessageBuffer(max_size=settings.analysis.buffer_size)

    # Services
    ai_analyzer = AIAnalyzer(llm, settings.analysis.confidence_threshold)
    birthday_parser = BirthdayParser(llm)
    meetup_detector = MeetupDetector(llm)
    quiz_service = QuizService(llm)
    reminder_service = ReminderService(llm)
    link_collector = LinkCollector()
    stats_service = StatsService()

    # Bot & Dispatcher
    bot = Bot(
        token=settings.bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Register middlewares (order matters)
    dp.message.middleware(DbSessionMiddleware(db))
    dp.message.middleware(
        MessageCollectorMiddleware(buffer, settings.analysis)
    )
    dp.message.middleware(RateLimitMiddleware(settings.rate_limit, buffer))

    # Also add DB middleware for callback queries
    dp.callback_query.middleware(DbSessionMiddleware(db))

    # Inject services into dispatcher workflow_data
    dp.workflow_data.update(
        {
            "message_buffer": buffer,
            "ai_analyzer": ai_analyzer,
            "birthday_parser": birthday_parser,
            "meetup_detector": meetup_detector,
            "quiz_service": quiz_service,
            "reminder_service": reminder_service,
            "link_collector": link_collector,
            "stats_service": stats_service,
            "settings": settings,
        }
    )

    # Register handlers
    register_all_handlers(dp)

    # Scheduler
    scheduler = AsyncIOScheduler()
    register_jobs(scheduler, bot=bot, db=db, buffer=buffer, settings=settings)
    scheduler.start()

    logger.info("Bot starting...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await db.close()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
