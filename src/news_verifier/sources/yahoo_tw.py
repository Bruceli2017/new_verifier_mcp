"""Yahoo奇摩新聞 (tw.news.yahoo.com): article parsing and search."""

import json
from urllib.parse import urlparse

from selectolax.lexbor import LexborHTMLParser

from news_verifier.http import get_text
from news_verifier.models import Article, NewsHit

BASE = "https://tw.news.yahoo.com"
SEARCH_URL = f"{BASE}/search"


class InvalidUrl(ValueError):
    pass


def is_yahoo_news_url(url: str) -> bool:
    u = urlparse(url)
    host = (u.hostname or "").lower()
    return u.scheme in ("http", "https") and (host == "tw.news.yahoo.com" or host == "tw.yahoo.com")


def _news_article_ld(tree: LexborHTMLParser) -> dict:
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text())
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") in ("NewsArticle", "Article", "ReportageNewsArticle"):
                return item
    return {}


def _meta(tree: LexborHTMLParser, key: str) -> str | None:
    node = tree.css_first(f'meta[property="{key}"]') or tree.css_first(f'meta[name="{key}"]')
    return node.attributes.get("content") if node else None


def _name(value) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, dict):
        return value.get("name") or None
    return value or None


def parse_article(url: str, html: str, max_chars: int = 6000) -> Article:
    tree = LexborHTMLParser(html)
    ld = _news_article_ld(tree)
    provider = ld.get("provider") if isinstance(ld.get("provider"), dict) else {}

    h1 = tree.css_first("h1")
    title = ld.get("headline") or _meta(tree, "og:title") or (h1.text(strip=True) if h1 else "")

    container = tree.css_first("div.atoms") or tree.css_first("article")
    paragraphs = [p.text(strip=True) for p in container.css("p")] if container else []
    body = "\n".join(p for p in paragraphs if p)
    truncated = len(body) > max_chars

    return Article(
        url=url,
        title=title,
        publisher=provider.get("name") or None,
        publisher_url=provider.get("url") or None,
        author=_name(ld.get("author")),
        published_at=ld.get("datePublished"),
        modified_at=ld.get("dateModified"),
        summary=_meta(tree, "og:description") or ld.get("description"),
        body=body[:max_chars],
        truncated=truncated,
    )


def parse_search(html: str, limit: int = 10) -> list[NewsHit]:
    tree = LexborHTMLParser(html)
    hits: list[NewsHit] = []
    for card in tree.css("li.stream-card"):
        link = card.css_first("h3 a[href]")
        if not link:
            continue
        snippet = card.css_first("p")
        publisher, published = None, None
        meta = card.css_first("div.text-px12")
        if meta:
            # e.g. "Newtalk新聞 ・ 4 小時前"
            parts = [s.strip() for s in meta.text(strip=True).split("・")]
            publisher = parts[0] or None
            published = parts[1] if len(parts) > 1 else None
        hits.append(
            NewsHit(
                title=link.text(strip=True),
                url=link.attributes["href"],
                publisher=publisher,
                published=published,
                snippet=snippet.text(strip=True) if snippet else None,
            )
        )
        if len(hits) >= limit:
            break
    return hits


class YahooTW:
    name = "yahoo_tw"

    def owns(self, url: str) -> bool:
        return is_yahoo_news_url(url)

    async def fetch_article(self, url: str, max_chars: int = 6000) -> Article:
        if not is_yahoo_news_url(url):
            raise InvalidUrl(f"Not a Yahoo TW news URL: {url}")
        final_url, html = await get_text(url)
        if not is_yahoo_news_url(final_url):
            raise InvalidUrl(f"Redirected away from Yahoo TW news: {final_url}")
        return parse_article(final_url, html, max_chars)

    async def search(self, query: str, limit: int = 10) -> list[NewsHit]:
        _, html = await get_text(SEARCH_URL, params={"p": query})
        return parse_search(html, limit)
