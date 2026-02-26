"""
End-to-end pipeline tests with all collaborators mocked.
"""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.collectors.base import Post


def _make_post(
    external_id: str = "pipeline-test-1",
    source: str = "stackoverflow",
    title: str = "Companies House API 429 rate limit exceeded",
    body: str = "",
    tags: list[str] | None = None,
) -> Post:
    return Post(
        source=source,
        external_id=external_id,
        url="https://stackoverflow.com/questions/123",
        title=title,
        body=body,
        tags=tags or [],
        created_at=datetime.utcnow(),
    )


class _FakeCollector:
    def __init__(self, posts: list[Post]):
        self._posts = posts
        self.lookback_seconds = 86400

    async def collect(self) -> list[Post]:
        return self._posts


@pytest.fixture(autouse=True)
def clear_dedup_cache():
    import src.dedup as dedup_module
    dedup_module._seen_in_memory.clear()
    yield
    dedup_module._seen_in_memory.clear()


@pytest.mark.asyncio
async def test_relevant_new_post_triggers_notification():
    """A relevant, unseen post should be notified once."""
    post = _make_post(tags=["companies-house"])
    collector = _FakeCollector([post])

    with patch("src.pipeline.send_notification", new_callable=AsyncMock) as mock_notify, \
         patch("src.pipeline.mark_seen", new_callable=AsyncMock) as mock_mark, \
         patch("src.pipeline.is_new", new_callable=AsyncMock, return_value=True):
        mock_notify.return_value = True

        from src.pipeline import run_collector
        summary = await run_collector(collector)

    mock_notify.assert_called_once()
    mock_mark.assert_called_once()
    assert summary["notified"] == 1
    assert summary["new"] == 1


@pytest.mark.asyncio
async def test_seen_post_not_notified():
    """A post already seen should not trigger a notification."""
    post = _make_post()
    collector = _FakeCollector([post])

    with patch("src.pipeline.send_notification", new_callable=AsyncMock) as mock_notify, \
         patch("src.pipeline.is_new", new_callable=AsyncMock, return_value=False):

        from src.pipeline import run_collector
        summary = await run_collector(collector)

    mock_notify.assert_not_called()
    assert summary["new"] == 0
    assert summary["notified"] == 0


@pytest.mark.asyncio
async def test_low_score_post_not_notified():
    """An irrelevant post (score < threshold) should not be notified."""
    post = _make_post(title="Python list comprehension tips")  # no CH/pain point keywords
    collector = _FakeCollector([post])

    with patch("src.pipeline.send_notification", new_callable=AsyncMock) as mock_notify:
        from src.pipeline import run_collector
        summary = await run_collector(collector)

    mock_notify.assert_not_called()
    assert summary["above_threshold"] == 0
    assert summary["notified"] == 0


@pytest.mark.asyncio
async def test_multiple_sources_all_polled():
    """run_all_collectors should run every collector passed to it."""
    collectors = [
        _FakeCollector([]),
        _FakeCollector([]),
        _FakeCollector([]),
        _FakeCollector([]),
    ]

    from src.pipeline import run_all_collectors
    results = await run_all_collectors(collectors)

    assert len(results) == 4


@pytest.mark.asyncio
async def test_collector_exception_does_not_crash_pipeline():
    """A collector that raises should return an empty summary, not crash."""
    class _BrokenCollector:
        lookback_seconds = 86400

        async def collect(self):
            raise RuntimeError("network down")

    with patch("src.pipeline.send_notification", new_callable=AsyncMock) as mock_notify:
        from src.pipeline import run_collector
        summary = await run_collector(_BrokenCollector())

    mock_notify.assert_not_called()
    assert summary["collected"] == 0


@pytest.mark.asyncio
async def test_pipeline_summary_counts_correctly():
    """run_collector summary should accurately count collected/threshold/new/notified."""
    relevant_new = _make_post("new-1", title="Companies House API 429 rate limit")
    relevant_seen = _make_post("seen-1", title="Companies House 429 rate limit exceeded")
    irrelevant = _make_post("irr-1", title="Python tips and tricks", body="", tags=[])

    collector = _FakeCollector([relevant_new, relevant_seen, irrelevant])

    async def fake_is_new(post):
        return post.external_id == "new-1"

    with patch("src.pipeline.is_new", side_effect=fake_is_new), \
         patch("src.pipeline.send_notification", new_callable=AsyncMock, return_value=True), \
         patch("src.pipeline.mark_seen", new_callable=AsyncMock):

        from src.pipeline import run_collector
        summary = await run_collector(collector)

    assert summary["collected"] == 3
    assert summary["above_threshold"] == 2  # relevant_new + relevant_seen
    assert summary["new"] == 1              # only relevant_new
    assert summary["notified"] == 1
