"""Draft reply templates, keyed by first matched pain point."""

from src.config import settings

_TEMPLATES: dict[str, str] = {
    "rate_limit": (
        "Hey, I ran into this exact problem a while back. The Companies House API "
        "has a hard 600 req/5-min cap and the errors are easy to miss in high-volume scripts. "
        "I ended up building a thin wrapper that handles backoff + caching — profiles cache "
        "for 24h, financials for 7 days — so I rarely hit the limit in practice. "
        "I've packaged it as a REST API if that helps: {api_base_url}. "
        "Happy to share more details."
    ),
    "ixbrl_parsing": (
        "iXBRL from Companies House filings is genuinely painful — the inline context "
        "references and taxonomy jumps make it tricky to extract even basic figures reliably. "
        "I built a parser that pulls structured financials (revenue, EBITDA, assets, etc.) "
        "directly from the document API and normalises them into clean JSON. "
        "Available here if useful: {api_base_url}. "
        "Let me know if you hit specific edge cases — happy to dig in."
    ),
    "director_network": (
        "This is a well-known pain point with the raw CH data — you have to paginate "
        "appointments for each officer and stitch the graph together yourself. "
        "I built an endpoint that traverses up to depth 2 (companies → officers → other companies) "
        "in one call and returns the full network as a node/edge list. "
        "API is here: {api_base_url}. "
        "No auth needed to try it out."
    ),
}

_DEFAULT_TEMPLATE = (
    "I've been working with the Companies House API and built a layer on top that "
    "might save you some time — handles caching, rate limiting, iXBRL parsing, and "
    "director network traversal. "
    "Worth a look: {api_base_url}."
)


def get_draft_reply(matched_pain_points: list[str]) -> str:
    """Return a draft reply based on the first matched pain point."""
    for point in matched_pain_points:
        if point in _TEMPLATES:
            return _TEMPLATES[point].format(api_base_url=settings.api_base_url)
    return _DEFAULT_TEMPLATE.format(api_base_url=settings.api_base_url)
