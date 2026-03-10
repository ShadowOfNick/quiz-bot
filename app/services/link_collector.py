import logging

from app.db.models import Link
from app.db.repositories.link_repo import LinkRepository
from app.utils.text_utils import extract_urls

logger = logging.getLogger(__name__)


class LinkCollector:
    async def collect_and_save(
        self,
        text: str,
        chat_id: int,
        user_id: int,
        repo: LinkRepository,
    ) -> list[Link]:
        urls = extract_urls(text)
        saved = []
        for url in urls:
            link = Link(
                chat_id=chat_id,
                user_id=user_id,
                url=url,
                context=text[:200],
            )
            try:
                await repo.save(link)
                saved.append(link)
            except Exception:
                logger.exception("Failed to save link: %s", url)
        return saved
