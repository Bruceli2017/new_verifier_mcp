"""Cofacts 真的假的 — crowd-sourced fact-check database (https://cofacts.tw)."""

from news_verifier.http import client
from news_verifier.models import FactCheckHit

API_URL = "https://api.cofacts.tw/graphql"
APP_ID = "RUMORS_SITE"

# Cofacts' own labels for each reply type.
RATINGS = {
    "RUMOR": "含有不實訊息",
    "NOT_RUMOR": "含有正確訊息",
    "OPINIONATED": "含有個人意見",
    "NOT_ARTICLE": "不在查證範圍",
}

QUERY = """
query ($text: String!, $first: Int!) {
  ListArticles(filter: {moreLikeThis: {like: $text}}, first: $first, orderBy: [{_score: DESC}]) {
    edges {
      score
      node {
        id
        text
        articleReplies(status: NORMAL) {
          createdAt
          reply { type text reference }
        }
      }
    }
  }
}
"""

TEXT_LIMIT = 500


def _clip(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip()
    return text if len(text) <= TEXT_LIMIT else text[:TEXT_LIMIT] + "…"


def parse(data: dict) -> list[FactCheckHit]:
    hits: list[FactCheckHit] = []
    for edge in data["data"]["ListArticles"]["edges"]:
        node = edge["node"]
        url = f"https://cofacts.tw/article/{node['id']}"
        for ar in node.get("articleReplies") or []:
            reply = ar.get("reply") or {}
            hits.append(
                FactCheckHit(
                    source="cofacts",
                    claim=_clip(node["text"]) or "",
                    rating=RATINGS.get(reply.get("type"), reply.get("type")),
                    reviewer="Cofacts 志工",
                    url=url,
                    date=ar.get("createdAt"),
                    explanation=_clip(reply.get("text")),
                    relevance=edge.get("score"),
                )
            )
    return hits


async def search(text: str, limit: int = 5) -> list[FactCheckHit]:
    resp = await client().post(
        API_URL,
        json={"query": QUERY, "variables": {"text": text, "first": limit}},
        headers={"x-app-id": APP_ID},
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errors"):
        raise RuntimeError(f"Cofacts error: {data['errors'][0].get('message')}")
    return parse(data)
