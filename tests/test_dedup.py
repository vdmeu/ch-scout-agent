"""
Tests for dedup module.

Supabase is always absent in tests (empty env vars), so we exercise
the in-memory fallback path.
"""

from datetime import datetime

import pytest

from src.collectors.base import Post
from src.scoring import ScoredPost


def _make_post(external_id: str = "test-123", source: str = "stackoverflow") -> Post:
    return Post(
        source=source,
        external_id=external_id,
        url=f"https://example.com/{external_id}",
        title="Test post",
        body="Companies House API 429",
        tags=[],
        created_at=datetime.utcnow(),
    )


def _make_scored(post: Post) -> ScoredPost:
    return ScoredPost(post=post, score=0.8, matched_pain_points=["rate_limit"])


@pytest.fixture(autouse=True)
def clear_in_memory_cache():
    """Reset in-memory dedup set between tests."""
    import src.dedup as dedup_module
    dedup_module._seen_in_memory.clear()
    yield
    dedup_module._seen_in_memory.clear()


@pytest.mark.asyncio
async def test_new_post_is_new():
    """A post never seen before should be is_new=True."""
    from src.dedup import is_new

    post = _make_post("never-seen-before")
    result = await is_new(post)
    assert result is True


@pytest.mark.asyncio
async def test_seen_post_is_not_new():
    """After mark_seen, the same post should return is_new=False."""
    from src.dedup import is_new, mark_seen

    post = _make_post("seen-post-456")
    scored = _make_scored(post)

    assert await is_new(post) is True
    await mark_seen(scored)
    assert await is_new(post) is False


@pytest.mark.asyncio
async def test_different_source_same_id_is_new():
    """Same external_id from a different source should be treated as new."""
    from src.dedup import is_new, mark_seen

    post_so = _make_post("shared-id", source="stackoverflow")
    post_hn = _make_post("shared-id", source="hackernews")

    await mark_seen(_make_scored(post_so))

    assert await is_new(post_so) is False
    assert await is_new(post_hn) is True


@pytest.mark.asyncio
async def test_different_id_same_source_is_new():
    """Different external_id from the same source should be treated as new."""
    from src.dedup import is_new, mark_seen

    post1 = _make_post("id-111", source="reddit")
    post2 = _make_post("id-222", source="reddit")

    await mark_seen(_make_scored(post1))

    assert await is_new(post1) is False
    assert await is_new(post2) is True
