from typing import List
from .base import BaseScraper, Article


class TheVergeArticle(Article):
    pass


class TheVergeScraper(BaseScraper):
    @property
    def rss_urls(self) -> List[str]:
        return ["https://www.theverge.com/rss/artificial-intelligence/index.xml"]

    def get_articles(self, hours: int = 24) -> List[TheVergeArticle]:
        return [
            TheVergeArticle(**article.model_dump())
            for article in super().get_articles(hours)
        ]


if __name__ == "__main__":
    scraper = TheVergeScraper()
    articles = scraper.get_articles(hours=48)
    print(f"Found {len(articles)} The Verge articles")
    for a in articles[:3]:
        print(f"- {a.title}")
