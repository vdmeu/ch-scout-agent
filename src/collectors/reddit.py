from datetime import datetime, timezone

import httpx

from src.collectors.base import BaseCollector, Post
from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://www.reddit.com/search.json"
_QUERIES = ["companies house api", "companies house iXBRL", "companies house rate limit"]


class RedditCollector(BaseCollector):
    """Collects recent Reddit posts via public JSON search (no OAuth)."""

    async def collect(self) -> list[Post]:
        seen_ids: set[str] = set()
        posts: list[Post] = []
        cutoff = datetime.now(timezone.utc).timestamp() - self.lookback_seconds
        headers = {"User-Agent": settings.reddit_user_agent}

        try:
            async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
                for query in _QUERIES:
                    params = {
                        "q": query,
                        "sort": "new",
                        "type": "link",
                        "limit": 25,
                    }
                    response = await client.get(_BASE_URL, params=params)
                    if response.status_code != 200:
                        logger.warning(
                            "reddit_api_error",
                            query=query,
                            status_code=response.status_code,
                        )
                        continue
                    data = response.json()

                    for child in data.get("data", {}).get("children", []):
                        item = child.get("data", {})
                        post_id = item.get("id", "")
                        if not post_id or post_id in seen_ids:
                            continue

                        created_ts = item.get("created_utc", 0)
                        if created_ts < cutoff:
                            continue

                        seen_ids.add(post_id)
                        subreddit = item.get("subreddit", "")
                        permalink = item.get("permalink", "")
                        url = f"https://www.reddit.com{permalink}" if permalink else item.get("url", "")

                        posts.append(
                            Post(
                                source="reddit",
                                external_id=post_id,
                                url=url,
                                title=item.get("title", ""),
                                body=item.get("selftext", ""),
                                tags=[subreddit] if subreddit else [],
                                created_at=datetime.fromtimestamp(created_ts, tz=timezone.utc),
                            )
                        )
        except Exception as exc:
            logger.warning("reddit_collect_failed", error=str(exc))
            return []

        logger.info("reddit_collected", count=len(posts))
        return posts
