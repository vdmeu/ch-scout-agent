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


async def send_notification(scored: ScoredPost) -> bool:
    """
    Send a Discord embed notification for a relevant post.

    Returns True on success, False on failure.
    No exception is raised — callers can treat notification failure as non-fatal.
    """
    if not settings.scout_webhook_url:
        logger.warning("no_webhook_url_configured")
        return False

    post = scored.post
    draft = get_draft_reply(scored.matched_pain_points)
    pain_points_str = ", ".join(scored.matched_pain_points) if scored.matched_pain_points else "general"

    embed = {
        "title": _truncate(post.title, 256),
        "url": post.url,
        "color": 0x5865F2,  # Discord blurple
        "fields": [
            {
                "name": "Source",
                "value": post.source.capitalize(),
                "inline": True,
            },
            {
                "name": "Score",
                "value": f"{scored.score:.2f}",
                "inline": True,
            },
            {
                "name": "Pain points",
                "value": pain_points_str,
                "inline": True,
            },
            {
                "name": "Draft reply",
                "value": _truncate(draft, 1024),
                "inline": False,
            },
        ],
        "footer": {"text": "ch-scout-agent • do not auto-post"},
    }

    if post.body:
        embed["description"] = _truncate(post.body)

    payload = {"embeds": [embed]}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(settings.scout_webhook_url, json=payload)
            if response.status_code in (200, 204):
                logger.info(
                    "notification_sent",
                    source=post.source,
                    external_id=post.external_id,
                    score=scored.score,
                )
                return True
            else:
                logger.warning(
                    "notification_failed",
                    status_code=response.status_code,
                    body=response.text[:200],
                )
                return False
    except Exception as exc:
        logger.warning("notification_exception", error=str(exc))
        return False
