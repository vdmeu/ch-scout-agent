from datetime import datetime, timezone

import httpx

from src.collectors.base import BaseCollector, Post
from src.utils.logging import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://hn.algolia.com/api/v1/search_by_date"
_QUERIES = ["companies house", "companies-house api", "iXBRL companies house"]


class HackerNewsCollector(BaseCollector):
    """Collects recent HN posts via Algolia search API."""

    async def collect(self) -> list[Post]:
        seen_ids: set[str] = set()
        posts: list[Post] = []
        cutoff = datetime.now(timezone.utc).timestamp() - self.lookback_seconds

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                for query in _QUERIES:
                    params = {
                        "query": query,
                        "tags": "story",
                        "hitsPerPage": 50,
                    }
                    response = await client.get(_BASE_URL, params=params)
                    if response.status_code != 200:
                        logger.warning(
                            "hackernews_api_error",
                            query=query,
                            status_code=response.status_code,
                        )
                        continue
                    data = response.json()

                    for hit in data.get("hits", []):
                        oid = str(hit.get("objectID", ""))
                        if oid in seen_ids:
                            continue

                        created_ts = hit.get("created_at_i", 0)
                        if created_ts < cutoff:
                            continue

                        seen_ids.add(oid)
                        body = hit.get("story_text") or hit.get("comment_text") or ""
                        posts.append(
                            Post(
                                source="hackernews",
                                external_id=oid,
                                url=hit.get("url") or f"https://news.ycombinator.com/item?id={oid}",
                                title=hit.get("title", ""),
                                body=body,
                                tags=[t for t in hit.get("_tags", []) if not t.startswith("author_")],
                                created_at=datetime.fromtimestamp(created_ts, tz=timezone.utc),
                            )
                        )
        except Exception as exc:
            logger.warning("hackernews_collect_failed", error=str(exc))
            return []

        logger.info("hackernews_collected", count=len(posts))
        return posts
