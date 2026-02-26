import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "stackoverflow_questions.json").read_text()
)

# Far-future cutoff so all fixture posts pass the recency filter
_FUTURE_TS = 9_999_999_999


def _mock_response(data: dict, status_code: int = 200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = data
    return response


def _make_collector(lookback: int = 999_999_999):
    from src.collectors.stackoverflow import StackOverflowCollector
    return StackOverflowCollector(lookback_seconds=lookback)


@pytest.mark.asyncio
async def test_collect_returns_post_objects():
    """Fixture JSON should produce a list of Post objects."""
    from src.collectors.base import Post

    collector = _make_collector()
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(FIXTURE))
        mock_client_class.return_value = mock_client

        posts = await collector.collect()

    assert len(posts) == 3
    for post in posts:
        assert isinstance(post, Post)


@pytest.mark.asyncio
async def test_collect_maps_fields_correctly():
    """Fields should map correctly from the API response."""
    collector = _make_collector()
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(FIXTURE))
        mock_client_class.return_value = mock_client

        posts = await collector.collect()

    first = posts[0]
    assert first.source == "stackoverflow"
    assert first.external_id == "77001234"
    assert "stackoverflow.com" in first.url
    assert "Companies House" in first.title
    assert first.body != ""
    assert isinstance(first.tags, list)
    assert first.created_at is not None


@pytest.mark.asyncio
async def test_collect_handles_empty_response():
    """Empty items list should return empty list (no error)."""
    collector = _make_collector()
    empty = {"items": [], "has_more": False}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(empty))
        mock_client_class.return_value = mock_client

        posts = await collector.collect()

    assert posts == []


@pytest.mark.asyncio
async def test_collect_handles_api_error():
    """429 response should return empty list without raising."""
    collector = _make_collector()

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response({}, status_code=429))
        mock_client_class.return_value = mock_client

        posts = await collector.collect()

    assert posts == []


@pytest.mark.asyncio
async def test_collect_only_fetches_recent_posts():
    """Posts older than lookback_seconds should be filtered out."""
    collector = _make_collector(lookback=1)  # 1 second → all fixture posts are old

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(FIXTURE))
        mock_client_class.return_value = mock_client

        posts = await collector.collect()

    assert posts == []
