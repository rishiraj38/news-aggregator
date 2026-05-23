from typing import List

from app.scrapers.base import Article, BaseScraper


class ConfigurableRSSScraper(BaseScraper):
    """Pull from one or many RSS URLs; stored as general RSS rows with caller-defined source slug."""

    def __init__(self, rss_urls: List[str]):
        self._rss_urls = [u.strip() for u in rss_urls if u and u.strip()]

    @property
    def rss_urls(self) -> List[str]:
        return self._rss_urls

    def get_articles(self, hours: int = 24) -> List[Article]:
        return [Article(**article.model_dump()) for article in super().get_articles(hours)]
