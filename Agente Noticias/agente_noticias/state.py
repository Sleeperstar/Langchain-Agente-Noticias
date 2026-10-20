"""Estado compartido del grafo LangGraph."""
from __future__ import annotations

from typing import TypedDict

from agente_noticias.schemas import Article, Briefing, EvaluatedArticle


class NewsState(TypedDict, total=False):
    """Estado que viaja entre nodos del grafo."""

    # Researcher
    raw_articles: list[Article]

    # History filter (anti-repeticion contra el historial SQLite)
    dropped_by_history: int

    # Evaluator
    scored_articles: list[EvaluatedArticle]

    # Ranker
    selected_articles: list[EvaluatedArticle]

    # Summarizer
    briefing: Briefing

    # Email writer
    subject: str
    html_body: str
    # (file path, Content-ID) of the images `html_body` references via cid:
    inline_images: list[tuple[str, str]]
    preview_path: str

    # Sender
    send_result: str
    # True only when Outlook accepted the message; persist_history relies on it.
    send_ok: bool
    run_id: str

    # Persist history
    briefing_id: str
