# News Verifier MCP

An MCP server that gathers evidence for judging whether a **Yahoo奇摩新聞** article or a free-text claim (e.g. a LINE forward) is credible.

The server does **not** decide "fake or real" itself. It returns structured evidence (the article and its original publisher, coverage from other outlets, fact-check matches) plus a rubric. The connected AI client then gives a **SUPPORTED / DISPUTED / UNVERIFIED** verdict with citations.

## Tools

| Tool | What it does |
|---|---|
| `verify(url? \| claim?, search_query?)` | One-shot evidence bundle: article + related Yahoo coverage + fact-checks + `hints` + `guidance` |
| `fetch_yahoo_article(url)` | Title, original publisher (中央社, 風傳媒, …), author, dates, body |
| `search_yahoo_news(query)` | Yahoo TW News search with publisher and age per hit |
| `search_fact_checks(query)` | [Cofacts](https://cofacts.tw) and, if configured, [Google Fact Check Tools](https://developers.google.com/fact-check/tools/api) (TFC, MyGoPen, AFP, …) |

There's also a `verify_news(target)` prompt that walks the client through the workflow.

**Search tip:** Yahoo search requires every word to match. Pass 2–4 short keywords (`大S 冥誕`), not full headlines. `verify` adds a `hints` entry when coverage is thin.

## Configuration

| Env var | Default | |
|---|---|---|
| `PORT` | `8080` | HTTP port |
| `HOST` | `0.0.0.0` | Bind address |
| `GOOGLE_FACTCHECK_API_KEY` | – | Optional. Without it, only Cofacts is queried and `errors` notes the skip |

Copy `.env.example` to `.env` and fill it in. The server doesn't auto-load `.env`, so pass the file explicitly: `uv run --env-file .env news-verifier` or `docker run --env-file .env ...`.

## Develop

```sh
uv sync
uv run pytest
uv run news-verifier            # HTTP: http://localhost:8080/mcp
uv run news-verifier --stdio    # stdio (what the bundle runs)
npx @modelcontextprotocol/inspector   # connect to http://localhost:8080/mcp (Streamable HTTP)
```

Endpoints: `/mcp` (MCP, stateless Streamable HTTP), `/health`, `/.well-known/mcp/server-card.json`.

## Try it (Claude Code)

Register the local server with Claude Code (stdio, no hosting needed):

```sh
claude mcp add news-verifier -- uv run --directory /path/to/news_verifier_mcp --no-dev news-verifier --stdio
claude mcp list        # should show news-verifier: ✓ Connected
```

Optional Google Fact Check key: add `-e GOOGLE_FACTCHECK_API_KEY=xxx` before the `--`.

Then start `claude` and ask in plain language:

> 網傳「多喝熱水可以殺死新冠病毒，喝熱水就不會被感染」，這是真的嗎？

Claude calls `verify` (and possibly `search_yahoo_news` / `search_fact_checks` for more evidence), then answers with a verdict such as **DISPUTED**. It cites the Cofacts entries rating this rumor 含有不實訊息 and any related news coverage.

You can also paste a Yahoo article URL: `這則新聞可信嗎？https://tw.news.yahoo.com/...`

Remove it with `claude mcp remove news-verifier`.

Other clients: install `news-verifier.mcpb` in Claude Desktop (Settings → Extensions → drag the file in), or use the MCP Inspector (see Develop).

## Publish to Smithery

This server is published as an **MCPB bundle**: Smithery distributes the file, and each user's MCP client runs it on their own machine over stdio. You don't host anything. On first launch, `uv` installs dependencies from `pyproject.toml` / `uv.lock`, so **users need [uv](https://docs.astral.sh/uv/) installed**.

> **Why `"type": "python"` with a `uv` command?** MCPB has a native `uv` type, but Smithery CLI 1.2.0 only accepts `bun` / `python` / `node` / `binary` and fails with *"Could not determine bundle runtime from manifest"*. Smithery installs the bundle using `server.mcp_config` as written, so the `uv run …` command is what actually runs.

> **Why no `tools` / `prompts` list in `manifest.json`?** Smithery copies those lists into its registry and requires full MCP definitions (`inputSchema`, object prompt arguments), while the MCPB schema rejects exactly those fields. So the manifest sets `tools_generated` / `prompts_generated` instead, and clients read the tools from the running server.

### First release

1. **Install the tools** (Node.js 20+):
   ```sh
   npm install -g smithery@latest
   smithery auth login
   ```
2. **Run the tests:**
   ```sh
   uv run pytest
   ```
3. **Validate and pack the bundle:**
   ```sh
   npx @anthropic-ai/mcpb validate manifest.json
   npx @anthropic-ai/mcpb pack . news-verifier.mcpb
   ```
   `.mcpbignore` keeps tests, Docker files and `.env` out of the bundle.
4. **(Recommended) Smoke-test the bundle from a clean folder**, the way a user's client would run it:
   ```sh
   mkdir -p /tmp/nv && unzip -o news-verifier.mcpb -d /tmp/nv
   (printf '%s\n' \
     '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"1"}}}' \
     '{"jsonrpc":"2.0","method":"notifications/initialized"}' \
     '{"jsonrpc":"2.0","id":2,"method":"tools/list"}'; sleep 5) \
   | uv run --directory /tmp/nv --no-dev --frozen news-verifier --stdio 2>/dev/null \
   | grep -o '"name":"[a-z_]*"'
   ```
   It should print the 4 tool names and exit after ~5 s. (`sleep` keeps input open so the server can answer before it sees end-of-input.) (Running the `uv run … --stdio` command alone prints nothing and waits for a client; that's normal. Ctrl+C to stop it.)
5. **Publish:**
   ```sh
   smithery mcp publish news-verifier.mcpb -n @<your-smithery-username>/news-verifier
   ```
6. **Check the listing** on smithery.ai: the 4 tools and the `verify_news` prompt should appear.

### New versions

1. Bump `version` in **both** `manifest.json` and `pyproject.toml` (also `version=` in `src/news_verifier/server.py`).
2. Run `uv lock` if dependencies changed.
3. Repeat steps 2–5 above.

### Users' settings

The optional Google Fact Check key is a masked setting the user fills in when installing (`user_config` in `manifest.json`). Leaving it empty uses Cofacts only.

### Alternative: hosted HTTP

The Docker image serves Streamable HTTP at `/mcp`:

```sh
docker build -t news-verifier .
docker run --env-file .env -p 8080:8080 news-verifier
```

To publish a hosted copy instead, deploy the image to any HTTPS host (Cloud Run, Fly.io, Render, …) and run `smithery mcp publish "https://<your-host>/mcp" -n @<your-smithery-username>/news-verifier`. `smithery.yaml` (`runtime: container`) is included in case your Smithery account offers building from a GitHub repo.

## Limitations

- Yahoo pages are scraped. If Yahoo changes its HTML, update `sources/yahoo_tw.py` and its fixtures in `tests/fixtures/`.
- Cofacts replies are crowd-sourced and its matching is fuzzy (see `relevance`). The rubric tells the client to weigh professional fact-checkers higher.
- Search only covers Yahoo TW News. Other outlets plug in via the `NewsSource` protocol in `sources/base.py`.
