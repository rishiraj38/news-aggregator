import os
import time
from typing import Optional

from app.scrapers.youtube import YouTubeScraper
from app.database.repository import Repository
from .base import BaseProcessService


TRANSCRIPT_UNAVAILABLE_MARKER = "__UNAVAILABLE__"

# Each fetch is individually timeout-bounded, but a throttled runner can still
# spend a minute per video. Cap the stage so it cannot eat the whole workflow.
TRANSCRIPT_STAGE_BUDGET_SECONDS = float(
    os.getenv("YT_TRANSCRIPT_STAGE_BUDGET_SECONDS", "420") or 420
)


class YouTubeTranscriptProcessor(BaseProcessService):
    def __init__(self):
        super().__init__()
        self.scraper = YouTubeScraper()
        self.repo = Repository()
        self.unavailable = 0
        self._started = time.monotonic()
        self._budget_exhausted = False

    def get_items_to_process(self, limit: Optional[int] = None) -> list:
        self._started = time.monotonic()
        return self.repo.get_youtube_videos_without_transcript(limit=limit)

    def _out_of_budget(self) -> bool:
        if TRANSCRIPT_STAGE_BUDGET_SECONDS <= 0:
            return False
        return (time.monotonic() - self._started) > TRANSCRIPT_STAGE_BUDGET_SECONDS

    def process_item(self, item) -> Optional[str]:
        if self._out_of_budget():
            if not self._budget_exhausted:
                self._budget_exhausted = True
                self.logger.warning(
                    "Transcript stage budget of %.0fs exhausted — skipping the "
                    "remaining videos this run.",
                    TRANSCRIPT_STAGE_BUDGET_SECONDS,
                )
            # Return None rather than the unavailable marker: the marker is a
            # permanent verdict (get_youtube_videos_without_transcript only picks
            # up rows where transcript IS NULL), and running out of time is not
            # the same as the transcript not existing. Leaving the row untouched
            # means the next run retries it.
            return None
        try:
            transcript_result = self.scraper.get_transcript(item.video_id)
            return transcript_result.text if transcript_result else TRANSCRIPT_UNAVAILABLE_MARKER
        except Exception:
            return TRANSCRIPT_UNAVAILABLE_MARKER

    def save_result(self, item, result: str) -> bool:
        success = self.repo.update_youtube_video_transcript(item.video_id, result)
        if result == TRANSCRIPT_UNAVAILABLE_MARKER:
            self.unavailable += 1
        return success

    def process(self, limit: Optional[int] = None) -> dict:
        result = super().process(limit=limit)
        result["unavailable"] = self.unavailable
        return result


def process_youtube_transcripts(limit: Optional[int] = None) -> dict:
    processor = YouTubeTranscriptProcessor()
    return processor.process(limit=limit)


if __name__ == "__main__":
    result = process_youtube_transcripts()
    print(f"Total videos: {result['total']}")
    print(f"Processed: {result['processed']}")
    print(f"Unavailable: {result['unavailable']}")
    print(f"Failed: {result['failed']}")

