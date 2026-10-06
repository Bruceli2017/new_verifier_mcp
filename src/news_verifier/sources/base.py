"""Interface every news source implements, so new outlets (e.g. Google News) can plug in."""

from typing import Protocol

from news_verifier.models import Article, NewsHit


class NewsSource(Protocol):
    name: str

    def owns(self, url: str) -> bool:
        """True if this source can fetch the given article URL."""
        ...

    async def fetch_article(self, url: str, max_chars: int) -> Article: ...

    async def search(self, query: str, limit: int) -> list[NewsHit]: ...
