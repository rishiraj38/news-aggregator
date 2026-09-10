# Helix — Autonomous News Curation

[![Tests](https://github.com/rishiraj38/news-aggregator/actions/workflows/tests.yml/badge.svg)](https://github.com/rishiraj38/news-aggregator/actions/workflows/tests.yml)
[![Daily Digest](https://github.com/rishiraj38/news-aggregator/actions/workflows/daily_digest.yml/badge.svg)](https://github.com/rishiraj38/news-aggregator/actions/workflows/daily_digest.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![LLM](https://img.shields.io/badge/LLM-Groq%20gpt--oss--120b-orange)](https://groq.com)

**An end-to-end pipeline that reads the news so subscribers don't have to.**

Every day, Helix ingests ~400 articles from 13 sources, summarises each one with an
LLM, ranks them against each subscriber's interests, and delivers a personalised
email — then publishes the top story as an Instagram card. It runs unattended on
GitHub Actions cron, with a Next.js dashboard where subscribers pick what they want.

---

## What it actually does

```
GitHub Actions cron (10:30 UTC)
│
├─ [1] Ingest ────────── 13 sources in parallel lanes
│    ├─ Labs & press     OpenAI · Anthropic · TechCrunch · The Verge
│    ├─ Topic bundles    technology · startups · politics · sports · cricket
│    ├─ Keyword lanes    one per subscriber-defined term (Google News + Hacker News)
│    └─ YouTube          Data API v3 search → transcript extraction
│
├─ [2] Digest ────────── LLM writes a title + summary per article
│    └─ Candidates are recency-sorted and round-robined across sources,
│       so no single feed can monopolise the batch
│
├─ [3] Curate ────────── LLM ranks digests 0–10 against each subscriber profile
│    └─ Chunked, TPM-aware, and degrades to neutral scores rather than
│       dropping a subscriber's whole email when a batch fails
│
├─ [4] Deliver ───────── Personalised HTML email over SMTP
│    └─ Diversified across topic lanes, with a reserved share for keyword hits
│
└─ [5] Publish ───────── Top unposted story → 1080×1350 card → Instagram Graph API
```

If a run breaks, it says so: the pipeline emails an operational alert and exits
non-zero rather than finishing green with nothing delivered.

---

## Features

**Personalisation**
- **Topic bundles** — five curated lanes; subscribers opt into any combination
- **Keyword lanes** — free-text terms ("ai agents", "nvidia earnings") each get their
  own nightly search across Google News and Hacker News. Results are routed *only*
  to the subscriber who asked for that term, and get a reserved share of the email
  so a busy news day can't crowd them out.
- **Diversification** — a subscriber on four bundles gets all four, not ten football stories

**Reliability**
- Proxy is best-effort with a direct fallback — an expired proxy plan degrades one
  request, it doesn't silently zero out the entire ingest
- Session-independent user snapshots, so a mid-run database reconnect can't
  detach ORM objects and collapse the send
- Bounded YouTube transcript fetches (per-request timeout + per-stage budget)
- Dual Groq API keys with rotation on rate limits, and batch-splitting on
  token-limit and JSON-validation failures
- Operational alerting: an email when a run errors, when ingestion dies, or when
  subscribers were processed but nothing was delivered

**Product**
- Next.js dashboard with Clerk auth, topic picker, and keyword editor
- Trial lifecycle with warning and expiry emails
- Instagram card generation (Pillow) and publishing

---

## Tech stack

| Layer | Choice |
|-------|--------|
| Pipeline | Python 3.12, SQLAlchemy, Pydantic, tenacity |
| LLM | Groq (`openai/gpt-oss-120b`) via the OpenAI-compatible SDK |
| Database | PostgreSQL (Neon), shared by the pipeline and the web app |
| Ingest | feedparser, YouTube Data API v3, youtube-transcript-api, HN Algolia |
| Images | Pillow (1080×1350 Instagram cards) |
| Frontend | Next.js (App Router), Clerk, Prisma, Tailwind |
| Orchestration | GitHub Actions cron — no always-on server |
| Tests | pytest (offline, no DB or API keys needed) |

---

## Quick start

**Prerequisites:** Python 3.12+, a free [Groq API key](https://console.groq.com),
PostgreSQL (or Docker), and a Gmail app password for SMTP.

```bash
git clone https://github.com/rishiraj38/news-aggregator.git
cd news-aggregator
uv sync
```

Create `app/.env`:

```bash
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_news_aggregator
GROQ_API_KEY=your_groq_key
GROQ_API_KEY2=optional_second_key_for_rotation
MY_EMAIL=you@gmail.com
APP_PASSWORD=your_gmail_app_password
YOUTUBE_API_KEY=optional_but_recommended
```

```bash
docker compose up -d          # local Postgres
uv run python main.py         # run the full pipeline
python -m pytest              # 58 tests, offline, ~0.5s
```

Useful during development:

```bash
# Only email one address, regardless of how many subscribers exist
DIGEST_EMAIL_TEST_ONLY=you@example.com python -m app.daily_runner

# Manage a subscriber's personalisation from the CLI
python scripts/set_user_topics.py you@example.com technology,startups
python scripts/set_user_keywords.py you@example.com "ai agents,nvidia earnings"

# Instagram card without publishing
uv run python publish_instagram_card.py --dry-run
```

The web app:

```bash
cd web && npm install && npm run dev
```

---

## Configuration

Everything is environment-driven. The most useful knobs:

| Var | Default | Purpose |
|-----|---------|---------|
| `DIGEST_BATCH_LIMIT` | `50` | Articles digested per run |
| `CURATOR_CHUNK_SIZE` | `12` | Digests per LLM ranking batch |
| `CURATOR_MAX_CANDIDATES` | `60` | Ranking pool per subscriber (bounds LLM spend) |
| `KEYWORD_MAX_TERMS` | `25` | Distinct keyword lanes ingested per run |
| `DISABLE_SCRAPER_PROXY` | – | `true` to skip the proxy entirely |
| `DIGEST_EMAIL_TEST_ONLY` | – | Restrict delivery to a single address |
| `FAIL_ON_ZERO_EMAILS` | `true` | Exit non-zero when nothing was delivered |
| `PIPELINE_ALERT_EMAIL` | `MY_EMAIL` | Where operational alerts go |

The full list lives in [CLAUDE.md](CLAUDE.md).

---

## Documentation

| Doc | What's in it |
|-----|--------------|
| [CLAUDE.md](CLAUDE.md) | Architecture reference, every env var, and a hard-won gotchas list |
| [INTERVIEW_GUIDE.md](INTERVIEW_GUIDE.md) | How to explain this project, including the production debugging story |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Deployment instructions |
| [docs/INTERVIEW_AND_ARCHITECTURE.md](docs/INTERVIEW_AND_ARCHITECTURE.md) | Deeper architecture notes and tradeoffs |

---

## Testing

```bash
python -m pytest
```

58 tests, fully offline — no database, network, or API keys. They cover the parts
that actually broke in production: keyword routing and privacy, source fairness in
digest selection, email slot allocation, reconnect-safe user handling, curator
degradation, and alert classification. CI runs them on every push alongside the
web typecheck and lint.

## License

MIT
