"""
APScheduler wiring.

Each collector gets its own interval job. The scheduler is started/stopped
as part of the FastAPI lifespan.

CLI usage (run all collectors once, print results, exit):
    python -m src.scheduler --run-now
"""

import asyncio
import sys

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from src.collectors.github_issues import GitHubIssuesCollector
from src.collectors.hackernews import HackerNewsCollector
from src.collectors.reddit import RedditCollector
from src.collectors.stackoverflow import StackOverflowCollector
from src.config import settings
from src.pipeline import run_all_collectors, run_collector
from src.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


def _build_collectors():
    lb = settings.lookback_seconds
    return [
        StackOverflowCollector(lookback_seconds=lb),
        HackerNewsCollector(lookback_seconds=lb),
        RedditCollector(lookback_seconds=lb),
        GitHubIssuesCollector(lookback_seconds=lb),
    ]


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the APScheduler instance (not yet started)."""
    scheduler = AsyncIOScheduler()
    collectors = _build_collectors()

    intervals = [
        (collectors[0], settings.poll_interval_stackoverflow),  # SO
        (collectors[1], settings.poll_interval_hackernews),     # HN
        (collectors[2], settings.poll_interval_reddit),         # Reddit
        (collectors[3], settings.poll_interval_github),         # GitHub
    ]

    for collector, interval_minutes in intervals:
        scheduler.add_job(
            run_collector,
            "interval",
            minutes=interval_minutes,
            args=[collector],
            id=type(collector).__name__,
            max_instances=1,
            coalesce=True,
        )

    return scheduler


# --------------------------------------------------------------------------- #
# CLI entry point: python -m src.scheduler --run-now
# --------------------------------------------------------------------------- #

async def _run_now() -> None:
    setup_logging()
    collectors = _build_collectors()
    logger.info("run_now_started", collector_count=len(collectors))
    results = await run_all_collectors(collectors)
    for r in results:
        logger.info("run_now_result", **r)


if __name__ == "__main__":
    if "--run-now" in sys.argv:
        asyncio.run(_run_now())
    else:
        print("Usage: python -m src.scheduler --run-now")
        sys.exit(1)
