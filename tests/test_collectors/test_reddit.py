import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

FIXTURE = json.loads(
    (Path(__file__).parent.parent / "fixtures" / "reddit_posts.json").read_text()
)


def _mock_response(data: dict, status_code: int = 200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = data
    return response


def _make_collector(lookback: int = 999_999_999):
    from src.collectors.reddit import RedditCollector
    return RedditCollector(lookback_seconds=lookback)


@pytest.mark.asyncio
async def test_collect_returns_post_objects():
    from src.collectors.base import Post

    collector = _make_collector()
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(FIXTURE))
        mock_client_class.return_value = mock_client

        posts = await collector.collect()

    assert len(posts) > 0
    for post in posts:
        assert isinstance(post, Post)


@pytest.mark.asyncio
async def test_collect_maps_fields_correctly():
    collector = _make_collector()
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(FIXTURE))
        mock_client_class.return_value = mock_client

        posts = await collector.collect()

    first = posts[0]
    assert first.source == "reddit"
    assert first.external_id == "abc123x"
    assert "reddit.com" in first.url
    assert first.title != ""
    assert "learnpython" in first.tags
    assert first.created_at is not None


@pytest.mark.asyncio
async def test_collect_handles_empty_response():
    collector = _make_collector()
    empty = {"kind": "Listing", "data": {"children": []}}

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
    collector = _make_collector(lookback=1)
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=_mock_response(FIXTURE))
        mock_client_class.return_value = mock_client

        posts = await collector.collect()

    assert posts == []
