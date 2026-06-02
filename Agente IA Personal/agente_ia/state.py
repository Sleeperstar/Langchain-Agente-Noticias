"""Estado compartido del grafo LangGraph."""
from __future__ import annotations

from typing import TypedDict

from agente_ia.schemas import Article, Briefing, EvaluatedArticle


class NewsState(TypedDict, total=False):
    """Estado que viaja entre nodos del grafo."""

    # Researcher
    raw_articles: list[Article]

    # Evaluator
    scored_articles: list[EvaluatedArticle]
    selected_articles: list[EvaluatedArticle]

    # Summarizer
    briefing: Briefing

    # Email writer
    subject: str
    html_body: str
    preview_path: str

    # Sender
    send_result: str
    run_id: str
