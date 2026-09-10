from datetime import datetime, timedelta, timezone
from typing import List, Optional
import logging
import os
import feedparser
import requests
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.proxies import WebshareProxyConfig

_logger = logging.getLogger(__name__)

# youtube-transcript-api builds a Session with no timeout and, with a Webshare
# proxy, retries a blocked video 10x. A throttled video could therefore hang the
# stage for tens of minutes and eat the whole workflow budget.
YT_TRANSCRIPT_TIMEOUT = float(os.getenv("YT_TRANSCRIPT_TIMEOUT", "20") or 20)
YT_TRANSCRIPT_RETRIES = int(os.getenv("YT_TRANSCRIPT_RETRIES", "2") or 2)


class _TimeoutSession(requests.Session):
    """Session that applies a default timeout to every request."""

    def __init__(self, timeout: float):
        super().__init__()
        self._timeout = timeout

    def request(self, *args, **kwargs):  # type: ignore[override]
        kwargs.setdefault("timeout", self._timeout)
        return super().request(*args, **kwargs)


class Transcript(BaseModel):
    text: str


class ChannelVideo(BaseModel):
    title: str
    url: str
    video_id: str
    published_at: datetime
    description: str
    transcript: Optional[str] = None


class YouTubeScraper:
    def __init__(self):
        proxy_config = None
        proxy_username = os.getenv("WEBSHARE_USERNAME")
        proxy_password = os.getenv("WEBSHARE_PASSWORD")

        if proxy_username and proxy_password:
            proxy_config = WebshareProxyConfig(
                proxy_username=proxy_username,
                proxy_password=proxy_password,
                retries_when_blocked=YT_TRANSCRIPT_RETRIES,
            )

        self.transcript_api = YouTubeTranscriptApi(
            proxy_config=proxy_config,
            http_client=_TimeoutSession(YT_TRANSCRIPT_TIMEOUT),
        )

    def _get_rss_url(self, channel_id: str) -> str:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    def _extract_video_id(self, video_url: str) -> str:
        if "youtube.com/watch?v=" in video_url:
            return video_url.split("v=")[1].split("&")[0]
        if "youtube.com/shorts/" in video_url:
            return video_url.split("shorts/")[1].split("?")[0]
        if "youtu.be/" in video_url:
            return video_url.split("youtu.be/")[1].split("?")[0]
        return video_url

    def get_transcript(self, video_id: str) -> Optional[Transcript]:
        try:
            transcript = self.transcript_api.fetch(video_id)
            text = " ".join([snippet.text for snippet in transcript.snippets])
            return Transcript(text=text)
        except (TranscriptsDisabled, NoTranscriptFound):
            return None
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Transcript unavailable for %s: %s", video_id, exc)
            return None

    def get_latest_videos(self, channel_id: str, hours: int = 24) -> list[ChannelVideo]:
        feed = feedparser.parse(self._get_rss_url(channel_id))
        if not feed.entries:
            return []

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        videos = []

        for entry in feed.entries:
            if "/shorts/" in entry.link:
                continue
            published_time = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
            if published_time >= cutoff_time:
                video_id = self._extract_video_id(entry.link)
                videos.append(
                    ChannelVideo(
                        title=entry.title,
                        url=entry.link,
                        video_id=video_id,
                        published_at=published_time,
                        description=entry.get("summary", ""),
                    )
                )

        return videos

    def scrape_channel(self, channel_id: str, hours: int = 150) -> list[ChannelVideo]:
        videos = self.get_latest_videos(channel_id, hours)
        result = []
        for video in videos:
            transcript = self.get_transcript(video.video_id)
            result.append(
                video.model_copy(
                    update={"transcript": transcript.text if transcript else None}
                )
            )
        return result


if __name__ == "__main__":
    scraper = YouTubeScraper()
    transcript: Transcript = scraper.get_transcript("jqd6_bbjhS8")
    print(transcript.text)
    channel_videos: List[ChannelVideo] = scraper.scrape_channel(
        "UCn8ujwUInbJkBhffxqAPBVQ", hours=200
    )
