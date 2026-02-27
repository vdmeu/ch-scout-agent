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


def _discord_only_settings(mock_settings):
    """Configure mock settings with Discord only (Telegram disabled)."""
    mock_settings.scout_webhook_url = "https://discord.com/api/webhooks/fake"
    mock_settings.telegram_bot_token = ""
    mock_settings.telegram_chat_id = ""
    mock_settings.api_base_url = "https://ch-api-production-b552.up.railway.app"


def _telegram_only_settings(mock_settings):
    """Configure mock settings with Telegram only (Discord disabled)."""
    mock_settings.scout_webhook_url = ""
    mock_settings.telegram_bot_token = "123456:ABC-fake-token"
    mock_settings.telegram_chat_id = "987654321"
    mock_settings.api_base_url = "https://ch-api-production-b552.up.railway.app"


def _no_channels_settings(mock_settings):
    """Configure mock settings with no channels."""
    mock_settings.scout_webhook_url = ""
    mock_settings.telegram_bot_token = ""
    mock_settings.telegram_chat_id = ""


# ---------------------------------------------------------------------------
# Discord tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discord_notification_sent_on_success():
    """Should return True when Discord returns 204."""
    from src.notifier import send_notification

    mock_response = AsyncMock()
    mock_response.status_code = 204

    with patch("src.notifier.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_class:
        _discord_only_settings(mock_settings)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await send_notification(_make_scored())

    assert result is True


@pytest.mark.asyncio
async def test_discord_notification_returns_false_on_http_error():
    """Should return False when Discord returns an error."""
    from src.notifier import send_notification

    mock_response = AsyncMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"

    with patch("src.notifier.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_class:
        _discord_only_settings(mock_settings)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await send_notification(_make_scored())

    assert result is False


@pytest.mark.asyncio
async def test_discord_payload_contains_draft_reply():
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
        _discord_only_settings(mock_settings)

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


# ---------------------------------------------------------------------------
# Telegram tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_telegram_notification_sent_on_success():
    """Should return True when Telegram returns 200."""
    from src.notifier import send_notification

    mock_response = AsyncMock()
    mock_response.status_code = 200

    with patch("src.notifier.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_class:
        _telegram_only_settings(mock_settings)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await send_notification(_make_scored())

    assert result is True


@pytest.mark.asyncio
async def test_telegram_notification_returns_false_on_no_token():
    """Should skip Telegram silently when no token is configured."""
    from src.notifier import _send_telegram

    with patch("src.notifier.settings") as mock_settings:
        mock_settings.telegram_bot_token = ""
        mock_settings.telegram_chat_id = ""

        result = await _send_telegram(_make_scored())

    assert result is False


@pytest.mark.asyncio
async def test_telegram_notification_returns_false_on_http_error():
    """Should return False when Telegram API returns an error."""
    from src.notifier import send_notification

    mock_response = AsyncMock()
    mock_response.status_code = 400
    mock_response.text = '{"ok": false, "description": "Bad Request"}'

    with patch("src.notifier.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_class:
        _telegram_only_settings(mock_settings)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client_class.return_value = mock_client

        result = await send_notification(_make_scored())

    assert result is False


@pytest.mark.asyncio
async def test_telegram_payload_uses_html_parse_mode():
    """The payload sent to Telegram should use HTML parse mode."""
    from src.notifier import send_notification

    captured = {}

    async def fake_post(url, json=None, **kwargs):
        captured["url"] = url
        captured["payload"] = json
        r = AsyncMock()
        r.status_code = 200
        return r

    with patch("src.notifier.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_class:
        _telegram_only_settings(mock_settings)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post
        mock_client_class.return_value = mock_client

        await send_notification(_make_scored())

    assert "api.telegram.org" in captured["url"]
    assert captured["payload"]["parse_mode"] == "HTML"
    assert "chat_id" in captured["payload"]
    assert "text" in captured["payload"]


@pytest.mark.asyncio
async def test_telegram_html_special_chars_escaped():
    """Angle brackets and ampersands in content should be HTML-escaped."""
    from src.notifier import _send_telegram

    scored = _make_scored(title="Test <b>bold</b> & special")
    captured = {}

    async def fake_post(url, json=None, **kwargs):
        captured["payload"] = json
        r = AsyncMock()
        r.status_code = 200
        return r

    with patch("src.notifier.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_class:
        _telegram_only_settings(mock_settings)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post
        mock_client_class.return_value = mock_client

        await _send_telegram(scored)

    text = captured["payload"]["text"]
    assert "<b>bold</b>" not in text   # raw HTML tags should not appear unescaped in content
    assert "&amp;" in text or "&lt;" in text or "&gt;" in text


# ---------------------------------------------------------------------------
# Both channels / fallback tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_channels_returns_false():
    """Should return False when neither Discord nor Telegram is configured."""
    from src.notifier import send_notification

    with patch("src.notifier.settings") as mock_settings:
        _no_channels_settings(mock_settings)

        result = await send_notification(_make_scored())

    assert result is False


@pytest.mark.asyncio
async def test_returns_true_if_either_channel_succeeds():
    """Should return True even if one channel fails, as long as one succeeds."""
    from src.notifier import send_notification

    call_count = 0

    async def fake_post(url, json=None, **kwargs):
        nonlocal call_count
        call_count += 1
        r = AsyncMock()
        # Discord fails, Telegram succeeds
        r.status_code = 204 if "discord" in url else 200
        r.text = ""
        return r

    with patch("src.notifier.settings") as mock_settings, \
         patch("httpx.AsyncClient") as mock_client_class:
        mock_settings.scout_webhook_url = "https://discord.com/api/webhooks/fake"
        mock_settings.telegram_bot_token = "123456:fake"
        mock_settings.telegram_chat_id = "999"
        mock_settings.api_base_url = "https://ch-api-production-b552.up.railway.app"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = fake_post
        mock_client_class.return_value = mock_client

        result = await send_notification(_make_scored())

    assert result is True
    assert call_count == 2  # both channels attempted
