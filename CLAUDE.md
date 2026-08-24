# Helix AI News Aggregator — Agent Guide

> **Purpose**: Autonomous AI-powered news pipeline that scrapes → digests → curates → emails → publishes Instagram cards on a daily cron.

## Quick Reference

| What | Command |
|------|---------|
| Run full pipeline locally | `uv run python main.py [hours] [top_n]` |
| Run pipeline (alt) | `python -m app.daily_runner` |
| Instagram card (dry-run) | `uv run python publish_instagram_card.py --dry-run` |
| Instagram card (publish) | `uv run python publish_instagram_card.py --publish` |
| Instagram diagnostics | `uv run python publish_instagram_card.py --instagram-diagnose` |
| Install deps | `uv sync` or `uv pip install -r requirements.txt` |
| Python version | ≥3.12 (pyproject.toml); CI uses 3.11 |
| Package manager | `uv` (astral) |
| Database | PostgreSQL (SQLAlchemy ORM) |
| LLM provider | Groq API (OpenAI-compatible SDK) |
| Current model | `openai/gpt-oss-120b` (was `llama-3.3-70b-versatile`, deprecated June 2026) |
| Frontend | Next.js + Clerk auth (in `web/`) |

---

## Architecture Overview

```
main.py / app/daily_runner.py          ← Entry point (GitHub Actions cron)
│
├─ [1/5] Scraping ─────────────────── app/runner.py + app/scrapers/*
│   ├── YouTubeScraper                 (yt-dlp search + transcript API)
│   ├── OpenAIScraper                  (RSS: openai.com/blog)
│   ├── AnthropicScraper               (RSS: anthropic.com)
│   ├── TechCrunchScraper              (RSS)
│   ├── TheVergeScraper                (RSS)
│   └── ConfigurableRSSScraper         (topic packs: BBC News/Sport/Cricket)
│
├─ [2/5] Anthropic markdown processing ── app/services/process_anthropic.py
├─ [3/5] YouTube transcript processing ── app/services/process_youtube.py
│
├─ [4/5] Digest generation ────────── app/services/process_digest.py
│   └── DigestAgent (LLM)              → Groq: title + summary per article
│       Capped by DIGEST_BATCH_LIMIT (default 100)
│
└─ [5/5] Personalization & email ──── app/services/process_email.py
    ├── CuratorAgent (LLM)             → Ranks digests per-user profile
    ├── EmailAgent (LLM)               → Generates personalized intro
    ├── Diversification                 → topic_packs/diversify.py
    └── Email sending                  → services/email_sender.py (SMTP)
```

### Instagram Card Pipeline (separate workflow)

```
publish_instagram_card.py
├── Fetches recent digests from DB
├── CuratorAgent ranks → picks top story
├── Resolves thumbnail (OG/YouTube/BBC)
├── render_breaking_news_card()        → app/services/news_graphic.py (Pillow)
├── Uploads JPEG (Cloudinary / anon hosts)
└── Publishes via Meta Instagram Graph API
```

---

## Project Structure

```
/
├── main.py                     # CLI entry: main(hours, top_n)
├── publish_instagram_card.py   # Standalone Instagram card script
├── pyproject.toml              # uv/pip deps, Python ≥3.12
├── requirements.txt            # Pinned deps for CI
├── render.yaml                 # Render.com deploy config
├── Dockerfile                  # Container build
│
├── app/
│   ├── .env                    # Local secrets (NEVER commit)
│   ├── config.py               # SEARCH_QUERIES for YouTube
│   ├── daily_runner.py         # Pipeline orchestrator (5 stages)
│   ├── runner.py               # Scraper registry & execution
│   ├── main.py                 # FastAPI/Streamlit dashboard (secondary)
│   │
│   ├── agent/
│   │   ├── base.py             # BaseAgent: Groq client, key rotation, retry
│   │   ├── digest_agent.py     # DigestAgent: article → {title, summary}
│   │   ├── curator_agent.py    # CuratorAgent: rank digests per user profile
│   │   └── email_agent.py      # EmailAgent: personalized email intro
│   │
│   ├── database/
│   │   ├── connection.py       # SQLAlchemy engine + session (PostgreSQL)
│   │   ├── models.py           # ORM models (7 tables)
│   │   ├── repository.py       # Data access layer (all CRUD)
│   │   └── schema_migrations.py # Additive column migrations
│   │
│   ├── scrapers/
│   │   ├── base.py             # BaseRSSScraper (feedparser)
│   │   ├── youtube.py          # YouTubeScraper (search + transcripts)
│   │   ├── openai.py           # OpenAI blog RSS
│   │   ├── anthropic.py        # Anthropic blog RSS
│   │   ├── techcrunch.py       # TechCrunch RSS
│   │   ├── theverge.py         # The Verge RSS
│   │   └── configurable_rss.py # Dynamic RSS for topic packs
│   │
│   ├── services/
│   │   ├── base.py             # BaseProcessService (process loop pattern)
│   │   ├── process_digest.py   # Digest batch processor
│   │   ├── process_email.py    # Email personalization + sending (main)
│   │   ├── process_anthropic.py # Anthropic markdown extraction
│   │   ├── process_youtube.py  # YouTube transcript processing
│   │   ├── process_curator.py  # Curator service wrapper
│   │   ├── email_sender.py     # SMTP sending + HTML templates
│   │   ├── thumbnail_resolve.py # best_youtube_still, OG image, BBC ichef
│   │   ├── news_graphic.py     # Pillow card renderer (1080×1350)
│   │   ├── instagram_publish.py # Meta Graph API + image hosting chain
│   │   ├── mail_links.py       # Email footer links (website, Instagram)
│   │   ├── search_agent.py     # YouTube search via yt-dlp
│   │   └── user_service.py     # User CRUD wrapper
│   │
│   ├── topic_packs/
│   │   ├── registry.py         # Topic definitions, RSS feed mappings
│   │   └── diversify.py        # Ensures email covers multiple topics
│   │
│   └── profiles/
│       └── user_profile.py     # Default admin profile (Rishi)
│
├── web/                        # Next.js frontend (Clerk auth, Prisma)
│   ├── src/app/                # App router pages
│   ├── src/components/         # React components
│   └── prisma/                 # Prisma schema
│
├── .github/workflows/
│   ├── daily_digest.yml        # Cron: 10:30 UTC daily
│   ├── instagram_post.yml      # Cron: 11:00 UTC daily (30min after digest)
│   └── docker-publish.yml      # Docker image builds
│
└── scripts/                    # Utility scripts
```

---

## Database Schema (PostgreSQL + SQLAlchemy)

7 tables, all use String primary keys (UUIDs or composite IDs):

| Table | Key | Purpose |
|-------|-----|---------|
| `youtube_videos` | `video_id` | Scraped YouTube videos + transcripts |
| `openai_articles` | `guid` | OpenAI blog RSS articles |
| `anthropic_articles` | `guid` | Anthropic blog RSS articles |
| `general_rss_articles` | `guid` | TechCrunch, The Verge, topic-pack RSS. `source` column identifies origin |
| `digests` | `id` (uuid) | LLM-generated title + summary per article. `article_type` + `article_id` link back |
| `users` | `id` (uuid) | Subscribers with JSON preferences, trial tracking |
| `recommendations` | `id` | Per-user ranked digest entries |
| `pipeline_runs` | `id` | Execution logs |

**Conventions**:
- Booleans stored as String `"true"/"false"` (not native bool)
- Floats/ints in Recommendation stored as String
- `image_url` columns added via `schema_migrations.py` (not alembic)
- No foreign keys enforced at DB level

---

## Agent System (LLM via Groq)

### BaseAgent (`app/agent/base.py`)
- Uses `openai` SDK pointed at `https://api.groq.com/openai/v1`
- **Dual API key rotation**: `GROQ_API_KEY` + `GROQ_API_KEY2`
- Auto-rotates on 429 (RPM); does NOT retry 413 (TPM/oversize)
- `tenacity` retry: 5 attempts, exponential backoff 4–60s
- All agents inherit and call `self.get_completion(messages, **kwargs)`

### DigestAgent
- Model: `openai/gpt-oss-120b`
- Input: article title + content (truncated to 8000 chars)
- Output: `DigestOutput(title, summary)` via JSON mode
- Called once per undigested article

### CuratorAgent
- Model: `openai/gpt-oss-120b`
- Ranks digests by relevance to user profile
- **Chunked batching**: splits digests into chunks of `CURATOR_CHUNK_SIZE` (default 6)
- **TPM-aware splitting**: if Groq rejects with 413, halves the chunk and retries
- Output: `List[RankedArticle]` with scores 0–10

### EmailAgent
- Model: `openai/gpt-oss-120b`
- Generates personalized greeting + intro from top-10 ranked articles
- Resolves thumbnails for each article via `thumbnail_resolve.py`

---

## Key Patterns

### Processing Pattern (`BaseProcessService`)
All batch processors follow the same loop in `app/services/base.py`:
```python
items = self.get_items_to_process(limit=limit)
for item in items:
    result = self.process_item(item)     # LLM call
    self.save_result(item, result)        # DB write
```
Subclasses: `DigestProcessor`, plus Anthropic/YouTube processors.

### Scraper Registry (`app/runner.py`)
Core scrapers + topic-pack scrapers registered as `(name, scraper_instance, save_func)` tuples.
`run_scrapers(hours)` iterates all, catches exceptions per-scraper.

### Topic Packs (`app/topic_packs/`)
- `registry.py`: defines `ALLOWED_TOPIC_IDS` = technology, politics, sports, cricket
- Maps `article_type` → topic via `_SOURCE_TOPIC` dict
- `digest_matches_topics()` gates which digests reach which users
- `diversify.py`: ensures the final top-N email isn't all one topic

### Thumbnail Resolution Chain (`app/services/thumbnail_resolve.py`)
1. Stored `image_url` from scraper
2. YouTube: tries `maxresdefault` → `sddefault` → `hqdefault` (skips tiny maxres)
3. BBC ichef: bumps width param to 976px
4. OG/Twitter meta tags from article URL (cached per send)

### Instagram Card Rendering (`app/services/news_graphic.py`)
- Canvas: 1080×1350 (portrait Instagram)
- Full-bleed cover crop with UnsharpMask sharpening
- Lower-third dark panel with red accent headline + white detail text
- Helix AI logo (built-in or custom PNG)
- Red ticker bar at bottom
- JPEG quality 97 with 4:4:4 chroma (`subsampling=0`)

---

## Environment Variables

### Required (pipeline)
| Var | Purpose |
|-----|---------|
| `DATABASE_URL` | PostgreSQL connection string |
| `GROQ_API_KEY` | Primary Groq LLM key |
| `MY_EMAIL` | SMTP sender email (Gmail) |
| `APP_PASSWORD` | Gmail app password for SMTP |

### Optional (pipeline)
| Var | Default | Purpose |
|-----|---------|---------|
| `GROQ_API_KEY2` | – | Secondary key for rate-limit rotation |
| `DIGEST_BATCH_LIMIT` | `100` | Max articles to digest per pipeline run |
| `DIGEST_EMAIL_TEST_ONLY` | – | Restrict email to single address |
| `CURATOR_CHUNK_SIZE` | `6` | Digests per Groq batch |
| `GROQ_CHUNK_SLEEP_SECONDS` | `10` | Sleep between curator batches |
| `GROQ_AFTER_KEY_ROTATE_SLEEP` | `2` | Pause after key failover |
| `HELIX_WEBSITE_URL` | – | Newsletter footer link |
| `HELIX_PRICING_URL` | – | Upgrade CTA link |
| `HELIX_INSTAGRAM_URL` | – | Instagram profile link in emails |
| `HELIX_INSTAGRAM_HANDLE` | – | @handle for email footer |

### Instagram publishing
| Var | Purpose |
|-----|---------|
| `META_ACCESS_TOKEN` | Instagram/Facebook Graph token |
| `INSTAGRAM_BUSINESS_ID` | IG Business account ID |
| `META_GRAPH_MEDIA_BASE` | Graph endpoint (default facebook; set to `https://graph.instagram.com/v21.0` for IG-login) |
| `CLOUDINARY_CLOUD_NAME` | Unsigned upload cloud name |
| `CLOUDINARY_UPLOAD_PRESET` | Unsigned upload preset |
| `META_PUBLIC_IMAGE_UPLOAD` | `auto` or `cloudinary` |
| `NEWS_GRAPHIC_TICKER` | Red bar text (default: "BREAKING NEWS") |
| `HELIX_LOGO_PATH` | Custom logo PNG path |

---

## GitHub Actions Workflows

### `daily_digest.yml`
- **Schedule**: 10:30 UTC daily (4:00 PM IST)
- **Runs**: `python -m app.daily_runner`
- **Secrets needed**: `DATABASE_URL`, `GROQ_API_KEY`, `GROQ_API_KEY2`, `MY_EMAIL`, `APP_PASSWORD`

### `instagram_post.yml`
- **Schedule**: 11:00 UTC daily (30 min after digest)
- **Runs**: `publish_instagram_card.py --publish`
- **Secrets needed**: all digest secrets + `META_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ID`, `CLOUDINARY_*`

### `docker-publish.yml`
- Docker image build and push

---

## Common Gotchas

1. **Model deprecation**: Groq retires models periodically. If you see `model_not_found`, query `GET https://api.groq.com/openai/v1/models` and update all 3 agents (`digest_agent.py`, `curator_agent.py`, `email_agent.py`).

2. **YouTube scraping timeouts**: YouTube aggressively throttles. The scraper retries 10× per video with no timeout cap, which can stall the pipeline for 30+ minutes. Consider adding explicit timeouts.

3. **413 TPM errors from Groq**: The curator splits chunks on 413 but digest_agent doesn't. If single articles are too large, the 8000-char truncation in `digest_agent.py:31` is the safeguard.

4. **Boolean columns are strings**: `user.is_active` is `"true"` not `True`. Always compare with `str(...).lower() != "true"`.

5. **No alembic migrations**: Schema changes use `schema_migrations.py` (additive ALTER TABLE only). New columns must handle NULL for existing rows.

6. **Env file loading order**: `app/.env` is loaded first, then root `.env`. Put secrets in `app/.env` locally.

7. **Digest IDs**: Format is `"{uuid}"`, but curator output sometimes includes quotes/whitespace. `_normalize_curator_digest_id()` in `publish_instagram_card.py` handles cleanup.

8. **Topic filtering**: Unknown `article_type` values pass through `digest_matches_topics()` (returns True). This is intentional — prevents silently dropping articles after migrations.

9. **Image quality**: Instagram cards use full-bleed cover crop with `UnsharpMask` sharpening. Small source thumbnails get `ImageEnhance.Sharpness(1.4)` to compensate for upscaling.

10. **Trial system**: 27-day trial with warnings at 2 days and 1 day remaining. Admins (`role="admin"`) are exempt. Expiration flags stored as string booleans.

---

## Adding a New Source

1. Create scraper in `app/scrapers/` extending `BaseRSSScraper` (or custom)
2. Add DB model in `app/database/models.py` if needed (or reuse `GeneralRSSArticle`)
3. Add bulk_create method in `app/database/repository.py`
4. Register in `app/runner.py` `_SCRAPER_REGISTRY_CORE` or as a topic pack in `app/topic_packs/registry.py`
5. Map `article_type` → topic in `registry.py` `_SOURCE_TOPIC` if non-tech

## Adding a New Topic Pack

1. Add entry to `RSS_TOPIC_FEED_SCRAPERS` in `app/topic_packs/registry.py`
2. Add topic ID to `ALLOWED_TOPIC_IDS` and `TOPIC_LABELS`
3. Add keyword detection in `normalize_user_topics()`
4. The scraper is auto-registered via `_topic_pack_scraper_rows()` in `runner.py`

---

## Dependencies (key)

| Package | Purpose |
|---------|---------|
| `openai` | Groq API client (OpenAI-compatible) |
| `sqlalchemy` | PostgreSQL ORM |
| `psycopg2-binary` | PostgreSQL driver |
| `pydantic` | Agent output schemas |
| `tenacity` | Retry/backoff for LLM calls |
| `feedparser` | RSS parsing |
| `pillow` | Instagram card image generation |
| `youtube-transcript-api` | YouTube transcript extraction |
| `requests` | HTTP client |
| `python-dotenv` | Env file loading |
| `streamlit` | Dashboard UI (secondary) |
