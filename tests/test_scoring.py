"""
TDD tests for the scoring engine.

Score formula:
  ch_context = 0.4 if any CH keyword in text+tags else 0.0
  per pain point: min(0.5, count_of_distinct_keyword_matches * 0.2)
  total = min(1.0, ch_context + sum(pain_point_scores))
"""

from datetime import datetime

import pytest

from src.collectors.base import Post
from src.scoring import score


def _post(title: str, body: str = "", tags: list[str] | None = None) -> Post:
    return Post(
        source="test",
        external_id="test-id",
        url="https://example.com",
        title=title,
        body=body,
        tags=tags or [],
        created_at=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# High-relevance posts
# ---------------------------------------------------------------------------


def test_rate_limit_post_scores_high():
    """CH context + rate limit keywords should score >= 0.8."""
    post = _post("Companies House API 429 rate limit exceeded")
    result = score(post)
    assert result.score >= 0.8
    assert "rate_limit" in result.matched_pain_points


def test_ixbrl_parsing_post_scores_high():
    """CH context + iXBRL keywords should score >= 0.8."""
    post = _post("How to parse iXBRL from Companies House filings")
    result = score(post)
    assert result.score >= 0.8
    assert "ixbrl_parsing" in result.matched_pain_points


def test_director_network_post_scores_high():
    """CH context + director network keywords should score >= 0.6."""
    post = _post(
        "Get all directors for list of companies",
        body="Using Companies House API to fetch all current officer appointments.",
    )
    result = score(post)
    assert result.score >= 0.6
    assert "director_network" in result.matched_pain_points


# ---------------------------------------------------------------------------
# Low-relevance / filtered posts
# ---------------------------------------------------------------------------


def test_unrelated_post_scores_below_threshold():
    """A post with no CH or pain point keywords should score very low."""
    post = _post("Python list comprehension tips and tricks")
    result = score(post)
    assert result.score < 0.3


def test_rate_limit_without_ch_context_scores_low():
    """Rate limit keywords alone (no CH context) should score below 0.5."""
    post = _post("Django 429 rate limit error handling")
    result = score(post)
    assert result.score < 0.5


def test_ch_context_only_scores_below_threshold():
    """CH context alone (no pain point keywords) should score below 0.5."""
    post = _post("Companies House website is down today")
    result = score(post)
    assert result.score < 0.5


# ---------------------------------------------------------------------------
# Boost / combination tests
# ---------------------------------------------------------------------------


def test_multiple_pain_points_boost_score():
    """Multiple pain point types should compound the score towards 1.0."""
    post = _post(
        "Companies House API rate limit and iXBRL parsing issues",
        body="Getting 429 errors and struggling to parse xbrl balance sheet data.",
    )
    result = score(post)
    assert result.score >= 0.9
    assert "rate_limit" in result.matched_pain_points
    assert "ixbrl_parsing" in result.matched_pain_points


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def test_score_bounded_0_to_1():
    """Score must always be in [0.0, 1.0] regardless of input."""
    posts = [
        _post(""),
        _post("Companies House 429 rate limit iXBRL director appointments"),
        _post("x" * 5000),
        _post(
            "Companies House API rate limit 429 iXBRL xbrl director officer appointments",
            body="rate limit rate-limit too many requests quota exceeded throttle "
                 "ixbrl xbrl annual accounts filed accounts financial statements "
                 "director network connected companies shared directors",
            tags=["companies-house", "rate-limiting", "xbrl"],
        ),
    ]
    for post in posts:
        result = score(post)
        assert 0.0 <= result.score <= 1.0, f"Score {result.score} out of range for: {post.title!r}"


def test_pain_points_list_accurate():
    """matched_pain_points should only contain types that actually matched."""
    post = _post("Companies House API 429 rate limit")
    result = score(post)
    # Should match rate_limit but NOT ixbrl_parsing or director_network
    assert "rate_limit" in result.matched_pain_points
    assert "ixbrl_parsing" not in result.matched_pain_points
    assert "director_network" not in result.matched_pain_points


def test_tags_contribute_to_scoring():
    """A post with a 'companies-house' tag should score higher than one without."""
    title = "How to handle 429 rate limit errors in batch processing"

    without_tag = _post(title, tags=[])
    with_tag = _post(title, tags=["companies-house"])

    score_without = score(without_tag).score
    score_with = score(with_tag).score

    assert score_with > score_without


def test_case_insensitive_matching():
    """Keywords should match regardless of case."""
    post = _post("COMPANIES HOUSE API RATE LIMIT 429")
    result = score(post)
    assert result.score >= 0.6
    assert "rate_limit" in result.matched_pain_points


def test_empty_post_scores_zero():
    """A completely empty post should score 0."""
    post = _post("", body="", tags=[])
    result = score(post)
    assert result.score == 0.0
    assert result.matched_pain_points == []
