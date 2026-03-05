# CLAUDE.md — ch-scout-agent

## Project

APScheduler + FastAPI service that monitors StackOverflow, Hacker News, Reddit, and GitHub
for Companies House API pain points and sends Discord (+ Telegram) alerts with draft replies.
Deployed on Railway.

## Local Environment

- **OS**: Windows 11, **Shell**: Git Bash
- **Project root**: `/c/users/eugen/claude-ch-proj/ch-scout-agent`
- **Python**: 3.12

## Key Commands

```bash
# Run unit tests (all mocked — no external deps needed)
cd /c/users/eugen/claude-ch-proj/ch-scout-agent && pytest tests/ -v

# Start dev server (hot reload)
cd /c/users/eugen/claude-ch-proj/ch-scout-agent && uvicorn src.main:app --reload

# Note: scheduler does NOT start in APP_ENV=development or APP_ENV=test
# Set APP_ENV=production locally only if you need to test scheduling
```

## Architecture

```
src/
├── main.py           FastAPI app + lifespan (scheduler start/stop)
├── config.py         pydantic-settings — reads .env
├── scheduler.py      APScheduler job definitions (one job per collector, every 6h)
├── pipeline.py       collect → score → dedup → notify orchestration
├── scoring.py        Relevance score [0.0–1.0] from keyword matching
├── dedup.py          Supabase dedup + in-memory fallback
├── notifier.py       Discord webhook + Telegram bot delivery
├── templates.py      Discord embed builder
├── collectors/
│   ├── base.py       Post dataclass
│   ├── stackoverflow.py
│   ├── hackernews.py
│   ├── reddit.py
│   └── github.py
└── utils/
    └── logging.py    structlog setup
```

### Scoring formula

`score = CH_context (0.4) + pain_point_matches (up to 0.5) → capped at 1.0`

- CH context: +0.4 if any CH keyword present ("companies house", "uk company", etc.)
- Pain points: rate_limit / ixbrl_parsing / director_network — each worth 0.2 per keyword, capped at 0.5 per group
- No developer/API language detected → score × 0.5 (filters general-public / legal posts)
- Only posts with `score >= MIN_RELEVANCE_SCORE (default 0.5)` are notified

### Deduplication

`scout_seen_posts` Supabase table — UNIQUE(source, external_id). In-memory set as fallback if
Supabase is unavailable. Posts are marked seen *after* successful notification.

### Collectors

| Collector | Source | Poll interval |
|-----------|--------|---------------|
| stackoverflow.py | SO API (/search/advanced) | 6h |
| hackernews.py | Algolia HN Search API | 6h |
| reddit.py | reddit.com JSON API (no auth) | 6h |
| github.py | GitHub Issues/Discussions search | 6h |

## Environment Variables

| Variable | Required | Where to get |
|----------|----------|--------------|
| `APP_ENV` | Yes | `production` / `development` / `test` |
| `SCOUT_WEBHOOK_URL` | Yes | credentials.md → Discord section |
| `SUPABASE_URL` | Yes | credentials.md → Supabase section |
| `SUPABASE_KEY` | Yes | credentials.md → Supabase service role key |
| `TELEGRAM_BOT_TOKEN` | Optional | credentials.md → Telegram section |
| `TELEGRAM_CHAT_ID` | Optional | credentials.md → Telegram section |
| `STACKOVERFLOW_API_KEY` | Optional | developer.stackexchange.com |
| `GITHUB_TOKEN` | Optional | github.com → Settings → Tokens |
| `MIN_RELEVANCE_SCORE` | No | default 0.5 |
| `LOOKBACK_SECONDS` | No | default 86400 (24h) |
| `POLL_INTERVAL_*` | No | default 360 (minutes) |

Never commit `.env`. Production env vars are set in Railway dashboard.

## Testing

Unit tests: `pytest tests/ -v` — all 64 tests are fully mocked (no external calls).

Cross-service smoke tests: `/c/users/eugen/claude-ch-proj/registrum-tests`
```bash
cd /c/users/eugen/claude-ch-proj/registrum-tests && npm run test:smoke
# Runs smoke/agent.test.ts — checks /health endpoint + scout_seen_posts table access
```

## Deployment

- **Platform**: Railway
- **Project ID**: `a636381b-ea65-43e9-bb63-4fc0f616a4e3`
- **Production URL**: `https://ch-scout-agent-production.up.railway.app`
- **Health endpoint**: `GET /health` → `{"status":"ok","service":"ch-scout-agent","environment":"production"}`
- **Config**: `railway.toml` is source of truth (healthcheck path, restart policy)
- **CI**: `.github/workflows/test.yml` runs on every push/PR to main

```bash
# Link Railway CLI to this project
cd /c/users/eugen/claude-ch-proj/ch-scout-agent && railway link --project a636381b-ea65-43e9-bb63-4fc0f616a4e3

# Deploy (Railway auto-deploys on push to main — this is manual override)
railway up

# Check logs
railway logs
```

## Things to Never Do

- Don't start the scheduler in test/development (`APP_ENV != production` guards this)
- Don't commit `.env` — production secrets in Railway dashboard
- Don't add Discord/Telegram credentials to version control
- Don't increase MIN_RELEVANCE_SCORE above 0.7 without re-testing the scoring suite
