"""
Collect → Score → Dedup → Notify pipeline.

Each collector runs independently; failures in one don't affect others.
"""

from src.collectors.base import BaseCollector
from src.config import settings
from src.dedup import is_new, mark_seen
from src.notifier import send_notification
from src.scoring import score
from src.utils.logging import get_logger

logger = get_logger(__name__)


async def run_collector(collector: BaseCollector) -> dict:
    """
    Run the full pipeline for a single collector.

    Returns a summary dict with counts for logging/monitoring.
    """
    name = type(collector).__name__
    summary = {
        "collector": name,
        "collected": 0,
        "above_threshold": 0,
        "new": 0,
        "notified": 0,
    }

    try:
        posts = await collector.collect()
    except Exception as exc:
        logger.error("pipeline_collect_failed", collector=name, error=str(exc))
        return summary

    summary["collected"] = len(posts)

    for post in posts:
        scored = score(post)

        if scored.score < settings.min_relevance_score:
            continue

        summary["above_threshold"] += 1

        if not await is_new(post):
            continue

        summary["new"] += 1

        notified = await send_notification(scored)
        await mark_seen(scored, notified=notified)

        if notified:
            summary["notified"] += 1

    logger.info("pipeline_run_complete", **summary)
    return summary


async def run_all_collectors(collectors: list[BaseCollector]) -> list[dict]:
    """Run the pipeline for every collector and return all summaries."""
    results = []
    for collector in collectors:
        result = await run_collector(collector)
        results.append(result)
    return results
