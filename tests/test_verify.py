import json
from pathlib import Path

import httpx
import pytest
import respx
from mcp import Client

from news_verifier import http, verify
from news_verifier.factcheck import cofacts, google_fc
from news_verifier.server import mcp
from news_verifier.sources.yahoo_tw import SEARCH_URL

FIXTURES = Path(__file__).parent / "fixtures"
ARTICLE_URL = "https://tw.news.yahoo.com/brazil-election-093000907.html"


def read(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def isolate(monkeypatch):
    http._cache.clear()
    monkeypatch.delenv(google_fc.ENV_KEY, raising=False)


@pytest.fixture
def mocked():
    with respx.mock(assert_all_called=False) as router:
        router.get(ARTICLE_URL).mock(return_value=httpx.Response(200, text=read("yahoo_article.html")))
        router.get(SEARCH_URL).mock(return_value=httpx.Response(200, text=read("yahoo_search.html")))
        router.post(cofacts.API_URL).mock(
            return_value=httpx.Response(200, json=json.loads(read("cofacts_vaccine.json")))
        )
        yield router


async def test_gather_from_url(mocked):
    b = await verify.gather(url=ARTICLE_URL)
    assert b.article.publisher == "風傳媒"
    assert b.query == b.article.title
    assert len(b.related_coverage) == 8
    assert "風傳媒" not in b.independent_publishers
    assert len(b.independent_publishers) == len(set(b.independent_publishers))
    assert b.fact_checks
    assert any("google_factcheck: skipped" in e for e in b.errors)


async def test_gather_from_claim_uses_search_query(mocked):
    b = await verify.gather(claim="很長的謠言內容" * 50, search_query="颱風")
    assert b.article is None
    assert b.query == "颱風"
    assert mocked.routes[1].calls.last.request.url.params["p"] == "颱風"


async def test_gather_reports_failed_source(mocked):
    mocked.post(cofacts.API_URL).mock(return_value=httpx.Response(503))
    b = await verify.gather(claim="颱風")
    assert b.fact_checks == []
    assert any(e.startswith("cofacts: HTTPStatusError") for e in b.errors)
    assert b.related_coverage


async def test_gather_hints_when_coverage_thin(mocked):
    mocked.get(SEARCH_URL).mock(return_value=httpx.Response(200, text="<html><ul></ul></html>"))
    b = await verify.gather(claim="一整句很長的網傳訊息")
    assert b.related_coverage == []
    assert len(b.hints) == 1
    assert "search_yahoo_news" in b.hints[0]


async def test_gather_no_hints_when_coverage_ok(mocked):
    b = await verify.gather(claim="颱風")
    assert b.hints == []


@pytest.mark.parametrize("kwargs", [{}, {"url": ARTICLE_URL, "claim": "x"}])
async def test_gather_requires_exactly_one_input(kwargs):
    with pytest.raises(ValueError):
        await verify.gather(**kwargs)


async def test_mcp_tools_and_prompt_registered():
    async with Client(mcp) as c:
        names = {t.name for t in (await c.list_tools()).tools}
        assert names == {"verify", "fetch_yahoo_article", "search_yahoo_news", "search_fact_checks"}
        prompts = {p.name for p in (await c.list_prompts()).prompts}
        assert prompts == {"verify_news"}


async def test_mcp_verify_tool_end_to_end(mocked):
    async with Client(mcp) as c:
        r = await c.call_tool("verify", {"url": ARTICLE_URL})
        assert not r.is_error
        assert r.structured_content["article"]["publisher"] == "風傳媒"


async def test_mcp_rejects_non_yahoo_url():
    async with Client(mcp) as c:
        r = await c.call_tool("fetch_yahoo_article", {"url": "http://169.254.169.254/"})
        assert r.is_error
        assert "Not a Yahoo TW news URL" in r.content[0].text
