from dataclasses import dataclass, field

from src.collectors.base import Post

# --------------------------------------------------------------------------- #
# Keyword definitions
# --------------------------------------------------------------------------- #

_CH_CONTEXT_KEYWORDS = [
    "companies house",
    "companies-house",
    "company house",
    "uk company",
    "uk companies",
    "ch api",
    "company information service",
    "company number",
    "companieshouse",
]

_PAIN_POINT_KEYWORDS: dict[str, list[str]] = {
    "rate_limit": [
        "rate limit",
        "rate-limit",
        "429",
        "too many requests",
        "api quota",
        "throttle",
        "quota exceeded",
    ],
    "ixbrl_parsing": [
        "ixbrl",
        "xbrl",
        "inline xbrl",
        "annual accounts",
        "filed accounts",
        "financial statements",
        "balance sheet data",
        "profit and loss",
        "taxonomy",
    ],
    "director_network": [
        "director network",
        "connected companies",
        "shared directors",
        "corporate network",
        "director",
        "directors",
        "officer",
        "appointments",
    ],
}

# Developer/technical context keywords.
# At least one must be present for a post to reach the notification threshold.
# If none are found the score is halved — this filters general public and legal
# posts that mention Companies House or directors without any API/code intent.
_DEV_CONTEXT_KEYWORDS = [
    # HTTP / API language
    "api", "endpoint", "http", "rest", "json", "sdk", "oauth", "webhook",
    "429", "status code", "curl", "rate limit", "rate-limit",
    # Programming languages
    "python", "javascript", "typescript", "nodejs", "ruby", "java", "php",
    "c#", ".net", "golang", "rust",
    # Developer actions / artefacts
    "library", "package", "module", "import", "parse", "parsing", "fetch",
    "script", "code", "developer", "integration", "data extraction",
    "query", "database", "request", "response", "error handling",
]

# Weight per matched keyword in a pain point group (capped at 0.5 per group)
_KEYWORD_WEIGHT = 0.2
_MAX_PAIN_POINT_SCORE = 0.5
_CH_CONTEXT_WEIGHT = 0.4
_NO_DEV_CONTEXT_MULTIPLIER = 0.5


# --------------------------------------------------------------------------- #
# Result type
# --------------------------------------------------------------------------- #


@dataclass
class ScoredPost:
    post: Post
    score: float
    matched_pain_points: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Scoring logic
# --------------------------------------------------------------------------- #


def _searchable_text(post: Post) -> str:
    """Combine title, body, and tags into a single lower-cased string."""
    parts = [post.title, post.body] + post.tags
    return " ".join(parts).lower()


def _count_keyword_matches(text: str, keywords: list[str]) -> int:
    """Count how many distinct keywords from the list appear in text."""
    return sum(1 for kw in keywords if kw.lower() in text)


def score(post: Post) -> ScoredPost:
    """
    Score a post for relevance to the CH Enrichment API.

    Returns a ScoredPost with:
    - score: float in [0.0, 1.0]
    - matched_pain_points: list of pain point keys that contributed

    Developer context check: if no programming/API language is detected the
    score is halved, pushing general-public and legal posts (which often
    mention Companies House or directors without API intent) below threshold.
    """
    text = _searchable_text(post)

    # CH context bonus
    ch_present = any(kw.lower() in text for kw in _CH_CONTEXT_KEYWORDS)
    ch_score = _CH_CONTEXT_WEIGHT if ch_present else 0.0

    # Pain point scores
    pain_scores: dict[str, float] = {}
    for pain_point, keywords in _PAIN_POINT_KEYWORDS.items():
        count = _count_keyword_matches(text, keywords)
        if count > 0:
            pain_scores[pain_point] = min(_MAX_PAIN_POINT_SCORE, count * _KEYWORD_WEIGHT)

    matched = sorted(pain_scores.keys())
    total = min(1.0, ch_score + sum(pain_scores.values()))

    # Halve score when no developer/technical language is present
    dev_present = any(kw.lower() in text for kw in _DEV_CONTEXT_KEYWORDS)
    if not dev_present:
        total = total * _NO_DEV_CONTEXT_MULTIPLIER

    return ScoredPost(post=post, score=round(total, 4), matched_pain_points=matched)
