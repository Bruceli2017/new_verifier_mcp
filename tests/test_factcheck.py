import json
from pathlib import Path

import httpx
import pytest
import respx

from news_verifier.factcheck import cofacts, google_fc

FIXTURES = Path(__file__).parent / "fixtures"

GOOGLE_RESPONSE = {
    "claims": [
        {
            "text": "喝熱水可以殺死新冠病毒",
            "claimant": "網傳訊息",
            "claimDate": "2020-02-01T00:00:00Z",
            "claimReview": [
                {
                    "publisher": {"name": "台灣事實查核中心", "site": "tfc-taiwan.org.tw"},
                    "url": "https://tfc-taiwan.org.tw/articles/0000",
                    "title": "【錯誤】網傳「喝熱水可以殺死新冠病毒」？",
                    "reviewDate": "2020-02-03T00:00:00Z",
                    "textualRating": "錯誤",
                    "languageCode": "zh",
                }
            ],
        }
    ]
}


def cofacts_fixture() -> dict:
    return json.loads((FIXTURES / "cofacts_vaccine.json").read_text(encoding="utf-8"))


def test_cofacts_parse_flattens_replies():
    hits = cofacts.parse(cofacts_fixture())
    assert len(hits) == 8  # 1 + 1 + 6 replies across 3 articles
    assert hits[0].source == "cofacts"
    assert hits[0].url == "https://cofacts.tw/article/3bux9mp9jpk54"
    assert hits[0].rating == "含有正確訊息"
    assert hits[1].rating == "含有不實訊息"
    assert hits[0].relevance > hits[1].relevance
    assert all(len(h.claim) <= cofacts.TEXT_LIMIT + 1 for h in hits)


@respx.mock
async def test_cofacts_search_sends_app_id():
    route = respx.post(cofacts.API_URL).mock(return_value=httpx.Response(200, json=cofacts_fixture()))
    hits = await cofacts.search("打疫苗 致死", limit=3)
    assert hits
    assert route.calls.last.request.headers["x-app-id"] == cofacts.APP_ID


@respx.mock
async def test_cofacts_graphql_error_raises():
    respx.post(cofacts.API_URL).mock(return_value=httpx.Response(200, json={"errors": [{"message": "boom"}]}))
    with pytest.raises(RuntimeError, match="boom"):
        await cofacts.search("x")


def test_google_parse():
    [hit] = google_fc.parse(GOOGLE_RESPONSE)
    assert hit.source == "google_factcheck"
    assert hit.rating == "錯誤"
    assert hit.reviewer == "台灣事實查核中心"
    assert hit.date == "2020-02-03T00:00:00Z"


def test_google_parse_empty():
    assert google_fc.parse({}) == []


async def test_google_requires_key(monkeypatch):
    monkeypatch.delenv(google_fc.ENV_KEY, raising=False)
    with pytest.raises(RuntimeError, match=google_fc.ENV_KEY):
        await google_fc.search("x")


@respx.mock
async def test_google_search_passes_key(monkeypatch):
    monkeypatch.setenv(google_fc.ENV_KEY, "test-key")
    route = respx.get(google_fc.API_URL).mock(return_value=httpx.Response(200, json=GOOGLE_RESPONSE))
    hits = await google_fc.search("熱水 新冠")
    assert len(hits) == 1
    assert route.calls.last.request.url.params["key"] == "test-key"
