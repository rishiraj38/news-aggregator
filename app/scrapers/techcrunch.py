from typing import List
from .base import BaseScraper, Article


class TechCrunchArticle(Article):
    pass


class TechCrunchScraper(BaseScraper):
    @property
    def rss_urls(self) -> List[str]:
        return ["https://techcrunch.com/category/artificial-intelligence/feed/"]

    def get_articles(self, hours: int = 24) -> List[TechCrunchArticle]:
        return [
            TechCrunchArticle(**article.model_dump())
            for article in super().get_articles(hours)
        ]


if __name__ == "__main__":
    scraper = TechCrunchScraper()
    articles = scraper.get_articles(hours=48)
    print(f"Found {len(articles)} TechCrunch articles")
    for a in articles[:3]:
        print(f"- {a.title}")
