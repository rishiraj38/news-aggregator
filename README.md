# Helix — Autonomous News Curation

[![Tests](https://github.com/rishiraj38/news-aggregator/actions/workflows/tests.yml/badge.svg)](https://github.com/rishiraj38/news-aggregator/actions/workflows/tests.yml)
[![Daily Digest](https://github.com/rishiraj38/news-aggregator/actions/workflows/daily_digest.yml/badge.svg)](https://github.com/rishiraj38/news-aggregator/actions/workflows/daily_digest.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![LLM](https://img.shields.io/badge/LLM-Groq%20gpt--oss--120b-orange)](https://groq.com)

**An end-to-end pipeline that reads the news so subscribers don't have to.**

Every day, Helix ingests ~400 articles from 13 sources, summarises each one with an
LLM, ranks them against each subscriber's interests, and delivers a personalised
email — then publishes the day's top stories as an Instagram carousel. It runs unattended on
GitHub Actions cron, with a Next.js dashboard where subscribers pick what they want.

---

## How it works

### The whole pipeline

```mermaid
flowchart TD
    CRON(["GitHub Actions cron · 10:30 UTC daily"]) --> ING

    ING["<b>1 · INGEST</b><br/>13 lanes fetched in sequence<br/><i>labs · topic bundles · keyword lanes · YouTube</i>"]
    ING -->|"~400 articles/day"| DBA[("articles")]

    DBA --> SEL["<b>2 · SELECT</b><br/><i>NOT EXISTS anti-join, newest-first,<br/>round-robin across sources</i>"]
    SEL -->|"60 balanced candidates"| DGA["<b>DigestAgent</b> · LLM<br/><i>article to title + summary</i>"]
    DGA --> DBD[("digests")]

    DBD --> CUR

    subgraph CUR["3 · CURATE — repeated per subscriber"]
        direction LR
        C1["Filter by<br/>topics + keywords"] --> C2["<b>CuratorAgent</b> · LLM<br/><i>score 0-10</i>"] --> C3["Diversify<br/><i>interleave lanes,<br/>reserve keyword slots</i>"]
    end

    CUR --> MAIL["Personalised HTML email<br/>via SMTP"]
    CUR -.->|"run looks broken"| AL["Operational alert<br/>+ non-zero exit"]

    DBD --> PUB["<b>4 · PUBLISH</b><br/><i>top 5 unposted stories to a<br/>1080x1350 carousel</i>"]
    PUB --> IG["Instagram<br/>Graph API<br/><i>cover + stories + CTA</i>"]

    WEB["Next.js dashboard<br/><i>Clerk auth · Prisma</i>"] <-->|"topics + keywords"| DBD

    style CRON fill:#4f46e5,color:#fff
    style MAIL fill:#059669,color:#fff
    style IG fill:#db2777,color:#fff
    style AL fill:#dc2626,color:#fff
    style WEB fill:#0284c7,color:#fff
    style DBA fill:#e0e7ff
    style DBD fill:#e0e7ff
```

### What gets fetched, and from where

```mermaid
flowchart LR
    subgraph SRC["Sources"]
        direction TB
        S1["openai.com/news/rss.xml"]
        S2["Anthropic news · research · engineering"]
        S3["techcrunch.com · AI + main feed"]
        S4["theverge.com/rss/index.xml"]
        S5["BBC News · World · Politics<br/>Guardian World · Politics"]
        S6["BBC Sport"]
        S7["BBC Cricket · ESPNcricinfo"]
        S8["BBC Tech · Guardian Tech · Ars<br/>Wired AI · MIT Tech Review"]
        S9["DeepMind blog · Hugging Face blog"]
        S10["YC blog · HN front page<br/>HN high-score stories"]
        S11["Google News search<br/>per subscriber keyword"]
        S12["Hacker News Algolia<br/>per subscriber keyword"]
        S13["YouTube Data API v3<br/>+ transcript extraction"]
    end

    S1 --> T1[("openai_articles")]
    S2 --> T2[("anthropic_articles")]
    S3 --> T3[("general_rss_articles<br/><i>source=techcrunch</i>")]
    S4 --> T4[("general_rss_articles<br/><i>source=theverge</i>")]
    S5 --> T5[("general_rss_articles<br/><i>source=topic_pol_bbcpolitics</i>")]
    S6 --> T6[("general_rss_articles<br/><i>source=topic_sport_bbcsport</i>")]
    S7 --> T7[("general_rss_articles<br/><i>source=topic_cricket_bbccricket</i>")]
    S8 --> T8[("general_rss_articles<br/><i>source=topic_tech_general</i>")]
    S9 --> T9[("general_rss_articles<br/><i>source=topic_tech_research</i>")]
    S10 --> T10[("general_rss_articles<br/><i>source=topic_startup_ychn</i>")]
    S11 --> T11[("general_rss_articles<br/><i>source=kw_slug_hash</i>")]
    S12 --> T11
    S13 --> T13[("youtube_videos")]
```

Every source writes its origin into the row. That origin becomes the digest's
`article_type`, which is what routing and topic filtering key off later — so
"where did this come from" survives all the way to the subscriber's inbox.

### How one story reaches the right person

```mermaid
flowchart TD
    ART["Article ingested<br/><i>article_type = topic_startup_ychn</i>"] --> DIG["Digest created<br/><i>id = article_type:article_id</i>"]

    DIG --> Q{"Is it a<br/>keyword lane?<br/><i>kw_*</i>"}

    Q -->|Yes| K{"Did THIS subscriber<br/>ask for that term?"}
    Q -->|No| T{"Is its topic in the<br/>subscriber's bundles?"}

    K -->|Yes| POOL["Enters ranking pool"]
    K -->|No| DROP1["Never shown<br/><i>keyword lanes are private</i>"]

    T -->|Yes| POOL
    T -->|No| DROP2["Filtered out"]
    T -->|"Unknown source"| POOL

    POOL --> TRIM["Trim to newest N<br/><i>keyword hits kept first</i>"]
    TRIM --> RANK["CuratorAgent scores 0-10"]
    RANK --> DIV["Diversify"]

    DIV --> R1["Reserved slots<br/>for keyword hits"]
    DIV --> R2["Remaining slots<br/>interleaved across<br/>the subscriber's lanes"]

    R1 --> MAIL["Top N in the email"]
    R2 --> MAIL

    style DROP1 fill:#dc2626,color:#fff
    style DROP2 fill:#78716c,color:#fff
    style MAIL fill:#059669,color:#fff
    style POOL fill:#4f46e5,color:#fff
```

### What happens when things break

Each of these was a real failure, and each now degrades instead of collapsing:

```mermaid
flowchart LR
    F1["Proxy is down"] --> H1["Retry directly<br/><i>log once, keep going</i>"] --> OK1["Ingest survives"]
    F2["A feed 404s"] --> H2["Log it, skip that endpoint"] --> OK2["Other 12 lanes unaffected"]
    F3["LLM returns bad JSON"] --> H3["Halve the batch, retry<br/><i>then neutral scores</i>"] --> OK3["Subscriber still gets an email"]
    F4["Groq rate-limits"] --> H4["Rotate API key<br/><i>413 splits instead</i>"] --> OK4["Run continues"]
    F5["Database SSL drops"] --> H5["Reconnect<br/><i>users held as snapshots</i>"] --> OK5["Send is unaffected"]
    F6["YouTube throttles"] --> H6["Per-request timeout<br/>+ per-stage budget"] --> OK6["Bounded, not stalled"]
    F7["Nothing was delivered"] --> H7["Alert email<br/>+ non-zero exit"] --> OK7["You find out same day"]

    style OK1 fill:#059669,color:#fff
    style OK2 fill:#059669,color:#fff
    style OK3 fill:#059669,color:#fff
    style OK4 fill:#059669,color:#fff
    style OK5 fill:#059669,color:#fff
    style OK6 fill:#059669,color:#fff
    style OK7 fill:#059669,color:#fff
```

### A run, end to end

```mermaid
sequenceDiagram
    autonumber
    participant CR as Cron
    participant PL as Pipeline
    participant EX as External sources
    participant DB as PostgreSQL
    participant AI as Groq LLM
    participant U as Subscriber

    CR->>PL: trigger daily run
    PL->>DB: ensure schema + indexes

    PL->>DB: read tracked keywords
    DB-->>PL: distinct terms, popularity ordered
    PL->>EX: fetch 13 lanes
    EX-->>PL: ~400 articles
    PL->>DB: upsert, deduplicated by guid

    PL->>DB: candidates without a digest
    Note over PL,DB: NOT EXISTS anti-join,<br/>newest-first per source
    DB-->>PL: 60, balanced across sources
    loop each article
        PL->>AI: summarise
        AI-->>PL: title + summary
    end
    PL->>DB: store digests

    loop each subscriber
        PL->>DB: profile + already-seen digests
        PL->>AI: rank candidates 0-10
        AI-->>PL: scores
        PL->>PL: diversify + reserve keyword slots
        PL->>DB: save recommendations
        PL->>U: personalised email
    end

    alt run looks broken
        PL->>U: operational alert
        PL->>CR: exit non-zero
    end
```

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
- **Three tiers** — Free gets a fixed daily briefing; Pro chooses topic bundles and
  tracks keywords; admins get everything plus the admin console. Enforced in the
  pipeline and the API, not just the UI.
- **Admin console** — every member with their plan and delivery health, one-click
  plan/role/status changes, and a daily email log showing who was emailed, whether
  it landed, and exactly which articles were in it
- Next.js dashboard with Clerk auth, topic picker, and keyword editor
- Trial lifecycle with warning and expiry emails
- **Instagram carousel** — a cover slide, one slide per story and a call-to-action
  slide, rendered with Pillow in a single design system, captioned with a rotating
  hashtag set, and published as one multi-image post

---

## Tech stack

| Layer | Choice |
|-------|--------|
| Pipeline | Python 3.12, SQLAlchemy, Pydantic, tenacity |
| LLM | Groq (`openai/gpt-oss-120b`) via the OpenAI-compatible SDK |
| Database | PostgreSQL (Neon), shared by the pipeline and the web app |
| Ingest | feedparser, YouTube Data API v3, youtube-transcript-api, HN Algolia |
| Images | Pillow (1080×1350 carousel slides, bundled Inter typeface) |
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
python -m pytest              # 103 tests, offline, ~0.5s
```

Useful during development:

```bash
# Only email one address, regardless of how many subscribers exist
DIGEST_EMAIL_TEST_ONLY=you@example.com python -m app.daily_runner

# Manage a subscriber's personalisation from the CLI
python scripts/set_user_topics.py you@example.com technology,startups
python scripts/set_user_keywords.py you@example.com "ai agents,nvidia earnings"

# Instagram carousel (writes JPEGs + prints the caption, publishes nothing)
uv run python publish_instagram_card.py --dry-run
uv run python publish_instagram_card.py --dry-run --slides 6   # more story slides
uv run python publish_instagram_card.py --dry-run --single     # old one-image card
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

103 tests, fully offline — no database, network, or API keys. They cover the parts
that actually broke in production: keyword routing and privacy, source fairness in
digest selection, email slot allocation, reconnect-safe user handling, curator
degradation, alert classification, and subscriber tier enforcement. CI runs them on every push alongside the
web typecheck and lint.

## License

MIT
