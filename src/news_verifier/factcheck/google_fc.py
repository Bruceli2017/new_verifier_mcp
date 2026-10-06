"""Google Fact Check Tools API — indexes ClaimReview from TFC, MyGoPen, AFP, etc."""

import os

from news_verifier.http import client
from news_verifier.models import FactCheckHit

API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
ENV_KEY = "GOOGLE_FACTCHECK_API_KEY"


def api_key() -> str | None:
    return os.environ.get(ENV_KEY) or None


def parse(data: dict) -> list[FactCheckHit]:
    hits: list[FactCheckHit] = []
    for claim in data.get("claims", []):
        for review in claim.get("claimReview", []):
            hits.append(
                FactCheckHit(
                    source="google_factcheck",
                    claim=claim.get("text", ""),
                    rating=review.get("textualRating"),
                    reviewer=(review.get("publisher") or {}).get("name"),
                    url=review.get("url"),
                    date=review.get("reviewDate") or claim.get("claimDate"),
                    explanation=review.get("title"),
                )
            )
    return hits


async def search(text: str, limit: int = 5, language: str = "zh") -> list[FactCheckHit]:
    key = api_key()
    if not key:
        raise RuntimeError(f"{ENV_KEY} not set")
    resp = await client().get(
        API_URL, params={"query": text, "languageCode": language, "pageSize": limit, "key": key}
    )
    resp.raise_for_status()
    return parse(resp.json())
