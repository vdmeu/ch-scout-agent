from datetime import datetime, timezone

import httpx

from src.collectors.base import BaseCollector, Post
from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

_BASE_URL = "https://api.github.com/search/issues"
_QUERIES = [
    "companies house api",
    "companies house xbrl",
    "companies house rate limit",
]


class GitHubIssuesCollector(BaseCollector):
    """Collects recent GitHub issues mentioning Companies House."""

    async def collect(self) -> list[Post]:
        seen_ids: set[str] = set()
        posts: list[Post] = []
        cutoff = datetime.now(timezone.utc).timestamp() - self.lookback_seconds

        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"

        try:
            async with httpx.AsyncClient(timeout=15.0, headers=headers) as client:
                for query in _QUERIES:
                    params = {
                        "q": f"{query} is:issue",
                        "sort": "created",
                        "order": "desc",
                        "per_page": 30,
                    }
                    response = await client.get(_BASE_URL, params=params)
                    if response.status_code != 200:
                        logger.warning(
                            "github_api_error",
                            query=query,
                            status_code=response.status_code,
                        )
                        continue
                    data = response.json()

                    for item in data.get("items", []):
                        issue_id = str(item.get("id", ""))
                        if not issue_id or issue_id in seen_ids:
                            continue

                        created_str = item.get("created_at", "")
                        try:
                            created_dt = datetime.fromisoformat(
                                created_str.replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            continue

                        if created_dt.timestamp() < cutoff:
                            continue

                        seen_ids.add(issue_id)
                        labels = [
                            lbl["name"]
                            for lbl in item.get("labels", [])
                            if isinstance(lbl, dict) and "name" in lbl
                        ]

                        posts.append(
                            Post(
                                source="github",
                                external_id=issue_id,
                                url=item.get("html_url", ""),
                                title=item.get("title", ""),
                                body=item.get("body") or "",
                                tags=labels,
                                created_at=created_dt,
                            )
                        )
        except Exception as exc:
            logger.warning("github_collect_failed", error=str(exc))
            return []

        logger.info("github_collected", count=len(posts))
        return posts
