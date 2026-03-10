from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Message:
    chat_id: int
    user_id: int
    message_id: int
    text: str = ""
    username: str | None = None
    display_name: str | None = None
    reply_to_message_id: int | None = None
    has_links: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    id: int | None = None


@dataclass
class User:
    user_id: int
    username: str | None = None
    display_name: str | None = None
    birthday: date | None = None
    first_seen_at: datetime = field(default_factory=datetime.now)


@dataclass
class QuizScore:
    chat_id: int
    user_id: int
    points: int
    is_correct: bool
    quiz_question: str = ""
    answered_at: datetime = field(default_factory=datetime.now)
    id: int | None = None


@dataclass
class Link:
    chat_id: int
    user_id: int
    url: str
    title: str | None = None
    context: str | None = None
    created_at: datetime = field(default_factory=datetime.now)
    id: int | None = None


@dataclass
class Reminder:
    chat_id: int
    user_id: int
    reminder_text: str
    remind_at: datetime
    created_at: datetime = field(default_factory=datetime.now)
    is_fired: bool = False
    id: int | None = None
