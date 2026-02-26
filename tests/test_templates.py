from src.templates import get_draft_reply


def test_rate_limit_template_returned():
    reply = get_draft_reply(["rate_limit"])
    assert "rate limit" in reply.lower() or "throttl" in reply.lower() or "600" in reply.lower()
    assert "ch-api-production-b552" in reply or "api_base_url" not in reply


def test_ixbrl_template_returned():
    reply = get_draft_reply(["ixbrl_parsing"])
    assert "ixbrl" in reply.lower() or "xbrl" in reply.lower()


def test_director_network_template_returned():
    reply = get_draft_reply(["director_network"])
    assert "director" in reply.lower() or "network" in reply.lower()


def test_first_pain_point_wins():
    """When multiple pain points match, the first one in the list is used."""
    reply_rate = get_draft_reply(["rate_limit", "ixbrl_parsing"])
    reply_ixbrl = get_draft_reply(["ixbrl_parsing", "rate_limit"])
    assert reply_rate != reply_ixbrl


def test_unknown_pain_point_returns_default():
    reply = get_draft_reply(["unknown_pain_point"])
    assert len(reply) > 0


def test_empty_pain_points_returns_default():
    reply = get_draft_reply([])
    assert len(reply) > 0


def test_all_templates_contain_api_url():
    """Every template should include a link to the API."""
    for points in [["rate_limit"], ["ixbrl_parsing"], ["director_network"], []]:
        reply = get_draft_reply(points)
        assert "ch-api-production" in reply or "http" in reply
