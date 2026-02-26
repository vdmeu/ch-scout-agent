# ch-scout-agent

Customer acquisition scout for the [CH Enrichment API](https://ch-api-production-b552.up.railway.app).

Monitors Stack Overflow, Hacker News, Reddit, and GitHub Issues for developers complaining about Companies House pain points (rate limits, iXBRL parsing, director networks), then sends a Discord alert with a contextual draft reply.

**Human-in-the-loop only** — no auto-posting, no AI, no auth required for any source.

---

## How it works

```
APScheduler (one job per source)
    │
    ▼
Collectors (SO · HN · Reddit · GitHub)  →  list[Post]
    │
    ▼
Scoring engine  →  ScoredPost (score 0–1, matched_pain_points)
    │  filter: score >= MIN_RELEVANCE_SCORE (default 0.5)
    ▼
Dedup (Supabase scout_seen_posts + in-memory fallback)
    │  filter: is_new == True
    ▼
Notifier (Discord embed + Supabase row insert)
```

### Scoring

| Component | Weight |
|-----------|--------|
| CH context keyword present | +0.4 |
| Each distinct pain-point keyword matched (per type) | +0.2, max 0.5/type |
| Total | capped at 1.0 |

**Pain point types:** `rate_limit`, `ixbrl_parsing`, `director_network`

Posts below `MIN_RELEVANCE_SCORE` (default 0.5) are silently dropped.

---

## Quick start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure
cp .env.example .env
# Edit .env — at minimum set SCOUT_WEBHOOK_URL

# 3. Run tests
pytest tests/ -v

# 4. Start the service (runs scheduler + health endpoint)
uvicorn src.main:app --reload

# 5. Trigger a one-shot run (useful for testing with real keys)
python -m src.scheduler --run-now
```

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SCOUT_WEBHOOK_URL` | — | Discord webhook URL (required for notifications) |
| `SUPABASE_URL` | — | Supabase project URL (shared with main API) |
| `SUPABASE_KEY` | — | Supabase anon key |
| `MIN_RELEVANCE_SCORE` | `0.5` | Posts below this score are dropped |
| `POLL_INTERVAL_STACKOVERFLOW` | `15` | Minutes between SO polls |
| `POLL_INTERVAL_HACKERNEWS` | `30` | Minutes between HN polls |
| `POLL_INTERVAL_REDDIT` | `30` | Minutes between Reddit polls |
| `POLL_INTERVAL_GITHUB` | `15` | Minutes between GitHub polls |
| `LOOKBACK_SECONDS` | `86400` | How far back to look (default: 24h) |
| `STACKOVERFLOW_API_KEY` | — | Optional — raises SO limit from 300 to 10K/day |
| `GITHUB_TOKEN` | — | Optional — raises GitHub limit from 60 to 5K/hr |
| `REDDIT_USER_AGENT` | `ch-scout-agent/1.0` | Required by Reddit API |

---

## Supabase schema

Run once in your Supabase SQL editor:

```sql
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
```

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check (used by Railway) |

---

## Project layout

```
src/
├── main.py           FastAPI app + scheduler lifespan
├── config.py         pydantic-settings
├── scoring.py        score(Post) → ScoredPost
├── templates.py      Draft replies per pain point
├── notifier.py       Discord webhook dispatch
├── dedup.py          Supabase dedup + in-memory fallback
├── pipeline.py       collect → score → dedup → notify
├── scheduler.py      APScheduler job wiring + CLI
├── collectors/
│   ├── base.py       Post dataclass + BaseCollector ABC
│   ├── stackoverflow.py
│   ├── hackernews.py
│   ├── reddit.py
│   └── github_issues.py
└── utils/
    └── logging.py    structlog (JSON in prod, console in dev)
```

---

## Deployment (Railway)

1. Create a new Railway service pointing to `ch-scout-agent/`
2. Set env vars in Railway dashboard (see Configuration above)
3. Railway uses `railway.toml` for healthcheck (`GET /health`)
4. Auto-deploys on push to main
