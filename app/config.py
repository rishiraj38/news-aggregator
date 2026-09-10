# Dynamic Search Queries (Replaces hardcoded channels)
SEARCH_QUERIES = [
    "AI News today",
    "LLM breakthroughs",
    "Artificial Intelligence Startup News",
    "Generative AI updates"
]

# Fallback channels used when YOUTUBE_API_KEY is unset or the Data API search
# returns nothing. IDs resolved from each channel's live page (canonical
# /channel/UC... URL + matching og:title) — YouTube rate-limits the RSS feed
# endpoint from many IPs, so a 404 here means "throttled", not "bad id".
FEATURED_CHANNELS = [
    "UCawZsQWqfGSbCI5yjkdVkTA",  # Matthew Berman
    "UCNJ1Ymd5yFuUPtn21xtRbbw",  # AI Explained (was UCcnwPBHHX1C7yJ1h734_q-A — wrong channel)
    "UCKelCK4ZaO6HeEI1KQjqzWA",  # The AI Daily Brief
    "UCbfYPyITQ-7l4upoX8nvctg",  # Two Minute Papers
    "UCZHmQk67mSJgfCCTn7xBfew",  # Yannic Kilcher
    "UCgfe2ooZD3VJPB6aJAnuQng",  # bycloud
]
