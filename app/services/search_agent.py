import logging
import subprocess
import json
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class SearchAgent:
    def __init__(self, top_n: int = 5):
        self.top_n = top_n

    def search_videos(self, query: str) -> List[Dict[str, Any]]:
        """
        Searches YouTube for videos matching the query using yt-dlp.
        Returns a list of video metadata dictionaries.
        """
        logger.info(f"🔍 Searching YouTube for: '{query}'")
        try:
            # yt-dlp search command: ytsearchN:query
            # --dump-json gives us full metadata
            # --flat-playlist ensures fast retrieval (doesn't resolve every video fully if not needed, but for search we usually want details)
            # Actually --dump-json is slow for search. --print-json --flat-playlist might be better but flat playlist doesn't have duration often.
            # Let's try standard dump-json for top 10.
            
            cmd = [
                "uv", "run", "yt-dlp",
                f"ytsearch{self.top_n+5}:{query}", # Fetch a few extra to filter
                "--dump-json",
                "--no-playlist",
                "--quiet",
                "--skip-download"
            ]
            
            # Run subprocess
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                logger.error(f"yt-dlp error: {stderr}")
                return []

            candidates = []
            
            # yt-dlp outputs one JSON object per line
            for line in stdout.strip().split('\n'):
                if not line: continue
                try:
                    video = json.loads(line)
                    
                    # Filtering Heuristics
                    
                    # 1. Duration (seconds) > 180 (3 mins)
                    duration = video.get('duration', 0)
                    if not duration or duration < 180:
                        continue
                        
                    candidates.append({
                        "video_id": video.get('id'),
                        "title": video.get('title'),
                        "url": video.get('webpage_url'),
                        "channel": video.get('uploader'),
                        "channel_id": video.get('uploader_id'),
                        "published_at": video.get('upload_date'), # Format: YYYYMMDD
                        "views": video.get('view_count'),
                        "description": video.get('description', '')
                    })
                except json.JSONDecodeError:
                    continue
            
            logger.info(f"   Found {len(candidates)} candidates for '{query}'")
            return candidates[:self.top_n]

        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            return []

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    agent = SearchAgent()
    results = agent.search_videos("AI News today")
    print(json.dumps(results, indent=2))
