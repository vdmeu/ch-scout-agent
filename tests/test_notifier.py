from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.collectors.base import Post
from src.scoring import ScoredPost


def _make_scored(
    title: str = "Companies House API 429",
    score: float = 0.8,
    pain_points: list[str] | None = None,
) -> ScoredPost:
    post = Post(
        source="stackoverflow",
        external_id="123",
        url="https://stackoverflow.com/questions/123",
        title=title,
        body="Rate limit error from Companies House",
        tags=["companies-house"],
        created_at=datetime.utcnow(),
    )
    return ScoredPost(post=post, score=score, matched_pain_points=pain_points or ["rate_limit"])


@pytest.mark.asyncio
async def test_notification_sent_on_success():
    """Should return True when Discord returns 204."""
    from src.notifier import send_notification

    mock_response = AsyncMock()
    mock_response.status_code = 204

    with patch("src.notifier.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_class:
        mock_settings.scout_webhook_url = "https://discord.com/api/webhooks/fake"
        mock_settings.api_base_url = "https://ch-api-production-b552.up.railway.app"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await send_notification(_make_scored())

    assert result is True


@pytest.mark.asyncio
async def test_notification_returns_false_on_no_webhook():
    """Should return False (not raise) when no webhook URL is configured."""
    from src.notifier import send_notification

    with patch("src.notifier.settings") as mock_settings:
        mock_settings.scout_webhook_url = ""

        result = await send_notification(_make_scored())

    assert result is False


@pytest.mark.asyncio
async def test_notification_returns_false_on_http_error():
    """Should return False (not raise) when Discord returns an error."""
    from src.notifier import send_notification

    mock_response = AsyncMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"

    with patch("src.notifier.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_class:
        mock_settings.scout_webhook_url = "https://discord.com/api/webhooks/fake"
        mock_settings.api_base_url = "https://ch-api-production-b552.up.railway.app"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await send_notification(_make_scored())

    assert result is False


@pytest.mark.asyncio
async def test_notification_returns_false_on_network_exception():
    """Should return False (not raise) on network failure."""
    from src.notifier import send_notification

    with patch("src.notifier.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_class:
        mock_settings.scout_webhook_url = "https://discord.com/api/webhooks/fake"
        mock_settings.api_base_url = "https://ch-api-production-b552.up.railway.app"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=ConnectionError("network down"))
        mock_client_class.return_value = mock_client

        result = await send_notification(_make_scored())

    assert result is False


@pytest.mark.asyncio
async def test_notification_payload_contains_draft_reply():
    """The payload sent to Discord should contain a draft reply field."""
    from src.notifier import send_notification

    captured_payload = {}

    async def fake_post(url, json=None, **kwargs):
        captured_payload.update(json or {})
        r = AsyncMock()
        r.status_code = 204
        return r

    with patch("src.notifier.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_class:
        mock_settings.scout_webhook_url = "https://discord.com/api/webhooks/fake"
        mock_settings.api_base_url = "https://ch-api-production-b552.up.railway.app"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post
        mock_client_class.return_value = mock_client

        await send_notification(_make_scored())

    embeds = captured_payload.get("embeds", [])
    assert len(embeds) == 1
    field_names = [f["name"] for f in embeds[0].get("fields", [])]
    assert "Draft reply" in field_names
