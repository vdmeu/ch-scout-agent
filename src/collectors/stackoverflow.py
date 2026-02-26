from datetime import datetime, timezone

import httpx

from src.collectors.base import BaseCollector, Post
from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://api.stackexchange.com/2.3/questions"
_TAGS = "companies-house;xbrl;uk-company-api"
_SITE = "stackoverflow"


class StackOverflowCollector(BaseCollector):
    """Collects recent Stack Overflow questions tagged with CH/XBRL tags."""

    async def collect(self) -> list[Post]:
        params = {
            "tagged": _TAGS,
            "site": _SITE,
            "order": "desc",
            "sort": "creation",
            "filter": "withbody",
            "pagesize": 50,
        }
        if settings.stackoverflow_api_key:
            params["key"] = settings.stackoverflow_api_key

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(_BASE_URL, params=params)
                if response.status_code != 200:
                    logger.warning(
                        "stackoverflow_api_error",
                        status_code=response.status_code,
                    )
                    return []
                data = response.json()
        except Exception as exc:
            logger.warning("stackoverflow_collect_failed", error=str(exc))
            return []

        cutoff = datetime.now(timezone.utc).timestamp() - self.lookback_seconds
        posts: list[Post] = []

        for item in data.get("items", []):
            created_ts = item.get("creation_date", 0)
            if created_ts < cutoff:
                continue

            posts.append(
                Post(
                    source="stackoverflow",
                    external_id=str(item["question_id"]),
                    url=item.get("link", ""),
                    title=item.get("title", ""),
                    body=item.get("body", ""),
                    tags=item.get("tags", []),
                    created_at=datetime.fromtimestamp(created_ts, tz=timezone.utc),
                )
            )

        logger.info("stackoverflow_collected", count=len(posts))
        return posts
