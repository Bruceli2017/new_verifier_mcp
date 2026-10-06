"""Gather evidence about a Yahoo article or a free-text claim."""

import asyncio

from news_verifier.factcheck import cofacts, google_fc
from news_verifier.models import EvidenceBundle, FactCheckHit, NewsHit
from news_verifier.sources.yahoo_tw import YahooTW

GUIDANCE = """\
You are judging credibility from the evidence above. Answer with exactly one verdict:
- SUPPORTED: multiple independent, established outlets report the same facts and no fact-check disputes it.
- DISPUTED: a fact-checker (TFC, MyGoPen, AFP, Cofacts) rates a matching claim false/misleading, or credible coverage contradicts it.
- UNVERIFIED: evidence is thin, only one outlet reports it, or fact-check matches are not clearly about the same claim.
Rules: cite URLs for every point; check that each fact-check hit is really about the same claim (Cofacts matches are
fuzzy, see `relevance`); professional fact-checkers outweigh Cofacts crowd replies; a source listed in `errors`
returned nothing, which is not evidence either way; never say "fake" with certainty.
Answer in the user's language (default 繁體中文)."""

QUERY_LIMIT = 200
THIN_COVERAGE = 3


def _short(text: str) -> str:
    return text.strip()[:QUERY_LIMIT]


async def gather(
    url: str | None = None,
    claim: str | None = None,
    search_query: str | None = None,
    limit: int = 8,
    yahoo: YahooTW | None = None,
) -> EvidenceBundle:
    if bool(url) == bool(claim):
        raise ValueError("Provide exactly one of `url` or `claim`.")
    yahoo = yahoo or YahooTW()

    article = await yahoo.fetch_article(url) if url else None
    subject = article.title if article else claim
    query = _short(search_query or subject)

    tasks = {"yahoo_search": yahoo.search(query, limit), "cofacts": cofacts.search(_short(subject), 5)}
    if google_fc.api_key():
        tasks["google_factcheck"] = google_fc.search(_short(subject), 5)
    results = dict(zip(tasks, await asyncio.gather(*tasks.values(), return_exceptions=True)))

    errors: list[str] = []
    coverage: list[NewsHit] = []
    fact_checks: list[FactCheckHit] = []
    for name, result in results.items():
        if isinstance(result, BaseException):
            errors.append(f"{name}: {type(result).__name__}: {result}")
        elif name == "yahoo_search":
            coverage = [h for h in result if not article or h.url != article.url]
        else:
            fact_checks.extend(result)
    if not google_fc.api_key():
        errors.append(f"google_factcheck: skipped ({google_fc.ENV_KEY} not configured)")

    hints: list[str] = []
    if len(coverage) < THIN_COVERAGE and "yahoo_search" not in "".join(errors):
        hints.append(
            f"Only {len(coverage)} related article(s) found for {query!r}. Yahoo search requires every word to match, "
            "so call `search_yahoo_news` again with 2-4 short keywords (names, places, key nouns) separated by spaces."
        )

    own = article.publisher if article else None
    publishers = list(dict.fromkeys(h.publisher for h in coverage if h.publisher and h.publisher != own))

    return EvidenceBundle(
        query=query,
        article=article,
        related_coverage=coverage,
        independent_publishers=publishers,
        fact_checks=fact_checks,
        errors=errors,
        hints=hints,
        guidance=GUIDANCE,
    )
