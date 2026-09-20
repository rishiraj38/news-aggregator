# Reel music beds

Excerpts used as the background track for Instagram Reels (`app/services/reel_video.py`).

| File | Source track | Artist | Licence |
|------|--------------|--------|---------|
| `bed-01-coexistenz.mp3` | *Coexistenz* (from "To Chill and Stay Awake") | Loyalty Freak Music | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) |
| `bed-02-traveling.mp3` | *Traveling in Your Mind* (same album) | Loyalty Freak Music | [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) |

Both are CC0 (public domain dedication): no attribution required, no licence fee,
and nothing for Instagram's Content ID to match — unlike chart music, which the API
cannot attach legally and which gets reels muted or blocked.

Each file is a 45-second excerpt taken from a point where the full arrangement is
playing, loudness-normalised to -16 LUFS so the beds sound consistent with each other.
Source: https://archive.org/details/LoyaltyFreakMusicTOCHILLANDSTAYAWAKE20170923132621469

To use a different track, set `HELIX_REEL_AUDIO=/path/to/file.mp3`, or drop more
`.mp3` files in this directory — the renderer rotates through them by day.
Instagram's own trending audio can only be added by posting from the app.
