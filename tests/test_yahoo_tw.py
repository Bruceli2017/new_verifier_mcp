from pathlib import Path

import httpx
import pytest
import respx

from news_verifier import http
from news_verifier.sources.yahoo_tw import (
    SEARCH_URL,
    InvalidUrl,
    YahooTW,
    is_yahoo_news_url,
    parse_article,
    parse_search,
)

FIXTURES = Path(__file__).parent / "fixtures"
ARTICLE_URL = "https://tw.news.yahoo.com/brazil-election-093000907.html"


@pytest.fixture(autouse=True)
def clear_cache():
    http._cache.clear()


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_parse_article_extracts_metadata_and_body():
    a = parse_article(ARTICLE_URL, read("yahoo_article.html"))
    assert a.title.startswith("巴西總統大選》")
    assert a.publisher == "風傳媒"
    assert a.publisher_url == "http://www.storm.mg"
    assert a.author == "李靖棠"
    assert a.published_at == "2026-10-06T09:30:00Z"
    assert "第一輪投票" in a.body
    assert not a.truncated


def test_parse_article_truncates_long_body():
    a = parse_article(ARTICLE_URL, read("yahoo_article.html"), max_chars=100)
    assert len(a.body) == 100
    assert a.truncated


def test_parse_search_extracts_cards():
    hits = parse_search(read("yahoo_search.html"), limit=20)
    assert len(hits) == 20
    first = hits[0]
    assert first.url.startswith("https://tw.news.yahoo.com/")
    assert first.publisher == "今日新聞NOWNEWS"
    assert first.published == "46 分鐘前"
    assert first.snippet


def test_parse_search_respects_limit():
    assert len(parse_search(read("yahoo_search.html"), limit=3)) == 3


@pytest.mark.parametrize(
    "url,ok",
    [
        ("https://tw.news.yahoo.com/x-123.html", True),
        ("https://tw.yahoo.com/x", True),
        ("https://evil.com/tw.news.yahoo.com", False),
        ("https://tw.news.yahoo.com.evil.com/x", False),
        ("file:///etc/passwd", False),
    ],
)
def test_is_yahoo_news_url(url, ok):
    assert is_yahoo_news_url(url) is ok


async def test_fetch_article_rejects_foreign_url():
    with pytest.raises(InvalidUrl):
        await YahooTW().fetch_article("http://169.254.169.254/latest/meta-data")


@respx.mock
async def test_fetch_and_search_over_http():
    respx.get(ARTICLE_URL).mock(return_value=httpx.Response(200, text=read("yahoo_article.html")))
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, text=read("yahoo_search.html")))
    src = YahooTW()
    assert (await src.fetch_article(ARTICLE_URL)).publisher == "風傳媒"
    assert len(await src.search("颱風", limit=5)) == 5
