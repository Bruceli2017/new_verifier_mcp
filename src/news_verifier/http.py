"""Shared HTTP client with a small TTL cache."""

import time

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
CACHE_TTL = 600  # seconds

_client: httpx.AsyncClient | None = None
_cache: dict[str, tuple[float, str, str]] = {}


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.5"},
            timeout=httpx.Timeout(15.0),
            follow_redirects=True,
        )
    return _client


async def get_text(url: str, params: dict | None = None) -> tuple[str, str]:
    """GET a page; returns (final_url, text). Successful responses are cached for CACHE_TTL."""
    key = str(httpx.URL(url, params=params))
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL:
        return hit[1], hit[2]
    resp = await client().get(url, params=params)
    resp.raise_for_status()
    _cache[key] = (time.monotonic(), str(resp.url), resp.text)
    return str(resp.url), resp.text
