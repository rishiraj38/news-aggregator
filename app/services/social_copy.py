"""
Instagram caption + hashtag builder.

Kept free of I/O so it can be unit tested: everything here is a pure function of
the stories, the date and the topics.

Hashtag strategy (Instagram allows 30; the cap here is lower on purpose):
  * a few broad tags for reach
  * niche tags per topic, which is what actually surfaces a small account
  * a rotating slice so consecutive posts don't repeat an identical block,
    which reads as spam to both viewers and ranking
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence

CAPTION_LIMIT = 2200  # Instagram's hard cap
MAX_HASHTAGS = 30

_BROAD = (
    "#ainews",
    "#technews",
    "#artificialintelligence",
    "#technology",
    "#tech",
)

_TOPIC_TAGS: dict[str, tuple[str, ...]] = {
    "technology": (
        "#ai",
        "#machinelearning",
        "#llm",
        "#openai",
        "#chatgpt",
        "#claudeai",
        "#genai",
        "#aitools",
        "#deeplearning",
        "#airesearch",
        "#futuretech",
        "#techupdates",
        "#innovation",
        "#coding",
        "#developer",
    ),
    "startups": (
        "#startup",
        "#startups",
        "#ycombinator",
        "#founders",
        "#venturecapital",
        "#saas",
        "#buildinpublic",
        "#entrepreneurship",
        "#techstartup",
        "#productlaunch",
    ),
    "politics": (
        "#worldnews",
        "#politics",
        "#geopolitics",
        "#currentaffairs",
        "#breakingnews",
        "#globalnews",
        "#policy",
    ),
    "sports": (
        "#sportsnews",
        "#sports",
        "#football",
        "#sportsupdate",
        "#gameday",
        "#athletes",
    ),
    "cricket": (
        "#cricket",
        "#cricketnews",
        "#cricketlovers",
        "#t20",
        "#cricketupdates",
        "#indiancricket",
    ),
}

_ALWAYS = ("#helix", "#dailynews", "#newsletter", "#aidaily")


@dataclass
class CaptionStory:
    title: str
    summary: str = ""
    url: str = ""
    topic: str = ""


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _shorten(text: str, limit: int) -> str:
    s = _clean(text)
    if len(s) <= limit:
        return s
    cut = s[:limit].rsplit(" ", 1)[0].rstrip(",.;:—-")
    return cut + "…"


def hashtags_for(
    topics: Iterable[str],
    date: Optional[datetime] = None,
    limit: int = 24,
) -> list[str]:
    """
    Deterministic for a given day, different across days.

    Broad tags always lead; the topic pool is rotated by day-of-year so two
    consecutive posts don't carry an identical hashtag block.
    """
    limit = max(1, min(limit, MAX_HASHTAGS))
    day = (date or datetime.now(timezone.utc)).timetuple().tm_yday

    picked: list[str] = []
    seen: set[str] = set()

    def add(tag: str) -> None:
        t = tag.lower()
        if t not in seen:
            seen.add(t)
            picked.append(t)

    for tag in _BROAD:
        add(tag)

    wanted = [t for t in topics if t in _TOPIC_TAGS] or ["technology"]
    pools = [_TOPIC_TAGS[t] for t in wanted]
    # Round-robin across the requested topics so a multi-topic post stays balanced.
    depth = 0
    while len(picked) < limit and depth < max(len(p) for p in pools):
        for pool in pools:
            if len(picked) >= limit:
                break
            add(pool[(day + depth) % len(pool)])
        depth += 1

    for tag in _ALWAYS:
        if len(picked) < limit:
            add(tag)

    return picked[:limit]


def build_carousel_caption(
    stories: Sequence[CaptionStory],
    *,
    site_url: str = "",
    handle: str = "",
    date: Optional[datetime] = None,
    hashtag_limit: int = 24,
) -> str:
    """Hook, numbered story list, CTA, then the hashtag block. Always within the 2200 limit."""
    when = date or datetime.now(timezone.utc)
    day_label = when.strftime("%d %B").lstrip("0")

    lines: list[str] = [
        f"Today in AI & tech — {day_label}",
        "",
        f"Swipe for the {len(stories)} stories worth your morning 👉",
        "",
    ]

    for i, story in enumerate(stories, start=1):
        lines.append(f"{i}. {_shorten(story.title, 120)}")
        if story.summary:
            lines.append(f"   {_shorten(story.summary, 150)}")
        lines.append("")

    lines.append("Which one matters most to you? Tell me in the comments 💬")
    lines.append("")
    if site_url:
        lines.append(f"Get this as a personalised email every morning → {site_url}")
    if handle:
        lines.append(f"Follow {handle} for the daily brief.")
    lines.append("")
    lines.append("—")
    lines.append("")

    topics = [s.topic for s in stories if s.topic]
    tags = " ".join(hashtags_for(topics, date=when, limit=hashtag_limit))

    body = "\n".join(lines)
    room = CAPTION_LIMIT - len(tags) - 2
    if len(body) > room:
        body = body[:room].rsplit("\n", 1)[0] + "\n"
    return f"{body}\n{tags}".strip()[:CAPTION_LIMIT]


def build_single_caption(
    story: CaptionStory,
    *,
    site_url: str = "",
    handle: str = "",
    date: Optional[datetime] = None,
    hashtag_limit: int = 24,
) -> str:
    """Caption for the one-image post (the fallback when only a single story is available)."""
    parts = [_shorten(story.title, 150)]
    if story.summary:
        parts += ["", _shorten(story.summary, 600)]
    if story.url:
        parts += ["", f"Source: {story.url}"]
    parts.append("")
    if site_url:
        parts.append(f"Your own AI news briefing, every morning → {site_url}")
    if handle:
        parts.append(f"Follow {handle} for the daily brief.")
    parts += ["", "—", ""]

    tags = " ".join(hashtags_for([story.topic] if story.topic else [], date=date, limit=hashtag_limit))
    body = "\n".join(parts)
    room = CAPTION_LIMIT - len(tags) - 2
    if len(body) > room:
        body = body[:room].rsplit("\n", 1)[0] + "\n"
    return f"{body}\n{tags}".strip()[:CAPTION_LIMIT]
