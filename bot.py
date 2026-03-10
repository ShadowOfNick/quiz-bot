import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
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

logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/webhook"


def create_bot_and_dispatcher(settings: Settings):
    """Create and configure bot, dispatcher, and all services."""
    # Database
    db = Database(settings.db.url if settings.db.url else f"sqlite+aiosqlite:///{settings.db.path}")

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

    return bot, dp, db, buffer, settings


async def on_startup_webhook(bot: Bot, base_url: str) -> None:
    """Set webhook on startup."""
    webhook_url = f"{base_url}{WEBHOOK_PATH}"
    await bot.set_webhook(webhook_url)
    logger.info(f"Webhook set to {webhook_url}")


async def run_webhook(settings: Settings) -> None:
    """Run bot in webhook mode (for Render / production)."""
    bot, dp, db, buffer, settings = create_bot_and_dispatcher(settings)

    await db.initialize()

    base_url = os.getenv("RENDER_EXTERNAL_URL", "")
    if not base_url:
        raise ValueError("RENDER_EXTERNAL_URL is not set. Cannot run in webhook mode.")

    # Scheduler
    scheduler = AsyncIOScheduler()
    register_jobs(scheduler, bot=bot, db=db, buffer=buffer, settings=settings)

    async def on_startup(app: web.Application) -> None:
        await on_startup_webhook(bot, base_url)
        scheduler.start()

    async def on_shutdown(app: web.Application) -> None:
        scheduler.shutdown()
        await bot.delete_webhook()
        await db.close()
        logger.info("Bot stopped.")

    # Create aiohttp app
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    # Health check endpoint (Render pings this)
    async def health(request: web.Request) -> web.Response:
        return web.Response(text="OK")

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    # Setup webhook handler
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    # Run on the port Render provides
    port = int(os.getenv("PORT", "10000"))
    logger.info(f"Starting webhook server on port {port}")
    web.run_app(app, host="0.0.0.0", port=port)


async def run_polling(settings: Settings) -> None:
    """Run bot in polling mode (for local development)."""
    bot, dp, db, buffer, settings = create_bot_and_dispatcher(settings)

    await db.initialize()

    # Scheduler
    scheduler = AsyncIOScheduler()
    register_jobs(scheduler, bot=bot, db=db, buffer=buffer, settings=settings)
    scheduler.start()

    logger.info("Bot starting in polling mode...")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await db.close()
        logger.info("Bot stopped.")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    settings = Settings()

    # If RENDER_EXTERNAL_URL is set, use webhook mode; otherwise polling
    if os.getenv("RENDER_EXTERNAL_URL"):
        logger.info("RENDER_EXTERNAL_URL detected — starting in webhook mode")
        asyncio.run(run_webhook(settings))
    else:
        logger.info("No RENDER_EXTERNAL_URL — starting in polling mode")
        asyncio.run(run_polling(settings))


if __name__ == "__main__":
    main()
