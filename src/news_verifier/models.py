"""Structured evidence returned by the MCP tools."""

from typing import Literal

from pydantic import BaseModel, Field


class Article(BaseModel):
    url: str
    title: str
    publisher: str | None = Field(None, description="Original outlet that wrote the story, e.g. 中央社, 風傳媒")
    publisher_url: str | None = None
    author: str | None = None
    published_at: str | None = None
    modified_at: str | None = None
    summary: str | None = None
    body: str = ""
    truncated: bool = False


class NewsHit(BaseModel):
    title: str
    url: str
    publisher: str | None = None
    published: str | None = Field(None, description="Relative time as shown by the source, e.g. '4 小時前'")
    snippet: str | None = None


class FactCheckHit(BaseModel):
    source: Literal["cofacts", "google_factcheck"]
    claim: str
    rating: str | None = Field(None, description="Verdict given by the fact-checker, e.g. 錯誤, 部分錯誤, 正確")
    reviewer: str | None = None
    url: str | None = None
    date: str | None = None
    explanation: str | None = None
    relevance: float | None = Field(None, description="Source's match score; low scores may be unrelated claims")


class EvidenceBundle(BaseModel):
    query: str
    article: Article | None = None
    related_coverage: list[NewsHit] = []
    independent_publishers: list[str] = []
    fact_checks: list[FactCheckHit] = []
    errors: list[str] = Field([], description="Sources that failed; absence of evidence from them is not evidence")
    hints: list[str] = Field([], description="Suggested follow-up tool calls when evidence is thin")
    guidance: str
