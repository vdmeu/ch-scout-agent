import httpx

from src.config import settings
from src.scoring import ScoredPost
from src.templates import get_draft_reply
from src.utils.logging import get_logger

logger = get_logger(__name__)

_MAX_BODY_LEN = 300


def _truncate(text: str, max_len: int = _MAX_BODY_LEN) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "…"


def _escape_html(text: str) -> str:
    """Escape special characters for Telegram HTML parse mode."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# Discord
# ---------------------------------------------------------------------------


async def _send_discord(scored: ScoredPost) -> bool:
    if not settings.scout_webhook_url:
        return False

    post = scored.post
    draft = get_draft_reply(scored.matched_pain_points)
    pain_points_str = ", ".join(scored.matched_pain_points) if scored.matched_pain_points else "general"

    embed = {
        "title": _truncate(post.title, 256),
        "url": post.url,
        "color": 0x5865F2,
        "fields": [
            {"name": "Source", "value": post.source.capitalize(), "inline": True},
            {"name": "Score", "value": f"{scored.score:.2f}", "inline": True},
            {"name": "Pain points", "value": pain_points_str, "inline": True},
            {"name": "Draft reply", "value": _truncate(draft, 1024), "inline": False},
        ],
        "footer": {"text": "ch-scout-agent • do not auto-post"},
    }
    if post.body:
        embed["description"] = _truncate(post.body)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(settings.scout_webhook_url, json={"embeds": [embed]})
            if response.status_code in (200, 204):
                logger.info("discord_notification_sent", source=post.source,
                            external_id=post.external_id, score=scored.score)
                return True
            logger.warning("discord_notification_failed", status_code=response.status_code,
                           body=response.text[:200])
            return False
    except Exception as exc:
        logger.warning("discord_notification_exception", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------


async def _send_telegram(scored: ScoredPost) -> bool:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return False

    post = scored.post
    draft = get_draft_reply(scored.matched_pain_points)
    pain_points_str = ", ".join(scored.matched_pain_points) if scored.matched_pain_points else "general"

    parts = [
        f"<b>{_escape_html(pain_points_str)}</b> | {post.source.capitalize()} | score {scored.score:.2f}",
        f'<a href="{post.url}">{_escape_html(_truncate(post.title, 200))}</a>',
    ]
    if post.body and post.body.strip():
        parts.append(f"\n<i>{_escape_html(_truncate(post.body, 400))}</i>")
    parts.append(f"\n💬 <code>{_escape_html(_truncate(draft, 280))}</code>")
    text = "\n".join(parts)

    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code == 200:
                logger.info("telegram_notification_sent", source=post.source,
                            external_id=post.external_id, score=scored.score)
                return True
            logger.warning("telegram_notification_failed", status_code=response.status_code,
                           body=response.text[:200])
            return False
    except Exception as exc:
        logger.warning("telegram_notification_exception", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Public interface — fans out to all configured channels
# ---------------------------------------------------------------------------


async def send_notification(scored: ScoredPost) -> bool:
    """
    Send a notification to all configured channels (Discord and/or Telegram).

    Returns True if at least one channel succeeded.
    Never raises — callers treat notification failure as non-fatal.
    """
    discord_ok = await _send_discord(scored)
    telegram_ok = await _send_telegram(scored)

    if not discord_ok and not telegram_ok:
        logger.warning("no_notification_channels_configured_or_all_failed")
        return False

    return True
