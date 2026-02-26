"""
Deduplication against Supabase scout_seen_posts + in-memory fallback.

Supabase schema (create once):

    CREATE TABLE scout_seen_posts (
      id BIGSERIAL PRIMARY KEY,
      source TEXT NOT NULL,
      external_id TEXT NOT NULL,
      url TEXT NOT NULL,
      title TEXT,
      matched_pain_points TEXT[],
      relevance_score DECIMAL(3,2),
      notified BOOLEAN DEFAULT false,
      responded BOOLEAN DEFAULT false,
      created_at TIMESTAMPTZ DEFAULT now(),
      UNIQUE(source, external_id)
    );
"""

from src.collectors.base import Post
from src.config import settings
from src.scoring import ScoredPost
from src.utils.logging import get_logger

logger = get_logger(__name__)

# In-memory fallback when Supabase is unavailable
_seen_in_memory: set[tuple[str, str]] = set()


def _get_supabase_client():
    """Return a Supabase client or None if credentials are absent."""
    if not settings.supabase_url or not settings.supabase_key:
        return None
    try:
        from supabase import create_client
        return create_client(settings.supabase_url, settings.supabase_key)
    except Exception as exc:
        logger.warning("supabase_client_init_failed", error=str(exc))
        return None


async def is_new(post: Post) -> bool:
    """
    Return True if this (source, external_id) has never been seen before.

    Checks Supabase first; falls back to in-memory set.
    Does NOT insert — call mark_seen() after notification.
    """
    key = (post.source, post.external_id)

    # In-memory fast path
    if key in _seen_in_memory:
        return False

    supabase = _get_supabase_client()
    if supabase is None:
        return True  # no Supabase → rely on in-memory only

    try:
        result = (
            supabase.table("scout_seen_posts")
            .select("id")
            .eq("source", post.source)
            .eq("external_id", post.external_id)
            .limit(1)
            .execute()
        )
        if result.data:
            _seen_in_memory.add(key)
            return False
        return True
    except Exception as exc:
        logger.warning("supabase_dedup_check_failed", error=str(exc))
        return True  # assume new on error


async def mark_seen(scored: ScoredPost, notified: bool = True) -> None:
    """
    Record the post in Supabase and the in-memory set.
    Silently ignores conflicts (UNIQUE constraint) to handle races.
    """
    post = scored.post
    key = (post.source, post.external_id)
    _seen_in_memory.add(key)

    supabase = _get_supabase_client()
    if supabase is None:
        return

    row = {
        "source": post.source,
        "external_id": post.external_id,
        "url": post.url,
        "title": post.title,
        "matched_pain_points": scored.matched_pain_points,
        "relevance_score": float(scored.score),
        "notified": notified,
    }

    try:
        supabase.table("scout_seen_posts").upsert(
            row, on_conflict="source,external_id"
        ).execute()
    except Exception as exc:
        logger.warning("supabase_mark_seen_failed", error=str(exc))
