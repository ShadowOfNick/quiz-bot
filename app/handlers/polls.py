import logging

from aiogram import Router
from aiogram.types import CallbackQuery, Message

from app.services.meetup_detector import MeetupDetector
from app.utils.message_buffer import MessageBuffer

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(lambda c: c.data == "meetup:create_poll")
async def create_meetup_poll(
    callback: CallbackQuery,
    meetup_detector: MeetupDetector,
    message_buffer: MessageBuffer,
) -> None:
    if not callback.message:
        return

    await callback.answer()
    await callback.message.edit_reply_markup(reply_markup=None)

    # Get recent messages for context
    chat_id = callback.message.chat.id
    recent = message_buffer.get_recent(chat_id, n=15)

    # Generate poll options based on context
    poll_data = await meetup_detector.generate_poll_options(recent)
    await callback.message.answer_poll(
        question=poll_data["question"],
        options=poll_data["options"],
        is_anonymous=False,
        allows_multiple_answers=True,
    )


@router.callback_query(lambda c: c.data == "meetup:skip")
async def skip_meetup_poll(callback: CallbackQuery) -> None:
    await callback.answer("Ок, без опроса!")
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
