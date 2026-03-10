from aiogram import Dispatcher

from app.handlers import callbacks, commands, group_messages, polls, quiz


def register_all_handlers(dp: Dispatcher) -> None:
    dp.include_router(commands.router)
    dp.include_router(quiz.router)
    dp.include_router(polls.router)
    dp.include_router(callbacks.router)
    # group_messages should be last — it's the catch-all for non-command messages
    dp.include_router(group_messages.router)
