"""News Verifier MCP server (Streamable HTTP)."""

import os
import sys

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from news_verifier import verify as verify_mod
from news_verifier.factcheck import cofacts, google_fc
from news_verifier.models import Article, EvidenceBundle, FactCheckHit, NewsHit
from news_verifier.sources.yahoo_tw import InvalidUrl, YahooTW

mcp = MCPServer(
    name="news-verifier",
    title="News Verifier",
    description="Gather evidence to judge whether Yahoo TW news or a claim is credible.",
    instructions=(
        "Use `verify` with a Yahoo TW news URL or a claim to get an evidence bundle, then follow its `guidance` "
        "to give a SUPPORTED / DISPUTED / UNVERIFIED verdict with citations. The other tools fetch individual pieces."
    ),
    version="0.1.0",
)
yahoo = YahooTW()


@mcp.tool()
async def verify(
    url: str | None = Field(None, description="A tw.news.yahoo.com article URL to verify"),
    claim: str | None = Field(None, description="A free-text claim or rumor to verify (e.g. a LINE forward)"),
    search_query: str | None = Field(
        None,
        description="2-4 short keywords separated by spaces for the news search, e.g. '大S 冥誕'. Strongly "
        "recommended: Yahoo search requires every word to match, so full headlines or sentences find almost nothing.",
    ),
) -> EvidenceBundle:
    """Collect evidence for a Yahoo TW news article OR a claim: the article itself, related Yahoo News coverage
    from other outlets, and matching fact-checks (Cofacts, Google Fact Check). Returns evidence plus a rubric;
    the verdict is yours to make."""
    try:
        return await verify_mod.gather(url=url, claim=claim, search_query=search_query, yahoo=yahoo)
    except (ValueError, InvalidUrl) as e:
        raise ToolError(str(e)) from e


@mcp.tool()
async def fetch_yahoo_article(
    url: str = Field(description="A tw.news.yahoo.com article URL"),
    max_chars: int = Field(6000, ge=200, le=20000, description="Truncate body to this many characters"),
) -> Article:
    """Fetch a Yahoo TW news article: title, original publisher (e.g. 中央社, 風傳媒), author, dates, body text."""
    try:
        return await yahoo.fetch_article(url, max_chars)
    except InvalidUrl as e:
        raise ToolError(str(e)) from e


@mcp.tool()
async def search_yahoo_news(
    query: str = Field(
        description="2-4 short keywords separated by spaces (繁體中文 works best); every word must match"
    ),
    limit: int = Field(10, ge=1, le=20),
) -> list[NewsHit]:
    """Search Yahoo TW News; each hit includes the original publisher and how long ago it was published."""
    return await yahoo.search(query, limit)


@mcp.tool()
async def search_fact_checks(
    query: str = Field(
        description="The full claim sentence, or keywords separated by spaces; short unspaced phrases often miss"
    ),
    limit: int = Field(5, ge=1, le=10),
) -> list[FactCheckHit]:
    """Look up a claim in fact-check databases: Cofacts (crowd-sourced, Taiwan) and, if configured,
    Google Fact Check Tools (TFC, MyGoPen, AFP, ...)."""
    hits = await cofacts.search(query, limit)
    if google_fc.api_key():
        hits += await google_fc.search(query, limit)
    return hits


@mcp.prompt()
def verify_news(target: str) -> str:
    """Verify a Yahoo TW news URL or a claim and give a graded verdict with citations."""
    arg = "url" if target.strip().startswith("http") else "claim"
    return (
        f"Call the `verify` tool with {arg}={target!r} and a `search_query` of 2-4 short keywords. If the bundle "
        "has `hints` or the evidence is thin, call `search_yahoo_news` or `search_fact_checks` with other keywords. "
        "Then answer following the bundle's `guidance`:\n\n" + verify_mod.GUIDANCE
    )


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


@mcp.custom_route("/.well-known/mcp/server-card.json", methods=["GET"])
async def server_card(_: Request) -> JSONResponse:
    """Static metadata for Smithery, in case its automatic scan fails."""
    dump = {"by_alias": True, "exclude_none": True, "mode": "json"}
    return JSONResponse(
        {
            "serverInfo": {"name": "news-verifier", "version": "0.1.0"},
            "authentication": {"required": False},
            "tools": [t.model_dump(**dump) for t in await mcp.list_tools()],
            "resources": [],
            "prompts": [p.model_dump(**dump) for p in await mcp.list_prompts()],
        }
    )


def main() -> None:
    # --stdio: local mode for MCPB bundles / desktop clients. Default: Streamable HTTP for hosting.
    if "--stdio" in sys.argv[1:] or os.environ.get("MCP_TRANSPORT") == "stdio":
        mcp.run("stdio")
        return
    mcp.run(
        "streamable-http",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8080")),
        stateless_http=True,
    )


if __name__ == "__main__":
    main()
