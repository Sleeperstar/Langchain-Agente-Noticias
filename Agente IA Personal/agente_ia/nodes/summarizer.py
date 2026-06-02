"""Summarizer node: produce headline + TL;DR + skill del dia."""
from __future__ import annotations

from datetime import date

from langchain.chat_models import init_chat_model

from agente_ia.config import get_model
from agente_ia.prompts import SUMMARIZER_SYSTEM, SUMMARIZER_USER_TEMPLATE
from agente_ia.schemas import Briefing
from agente_ia.state import NewsState


def _format_articles_block(selected) -> str:
    lines = []
    for i, item in enumerate(selected, start=1):
        a, e = item.article, item.evaluation
        lines.append(
            f"{i}. [{e.relevance_score}/10] {a.title}\n"
            f"   Categoria: {e.category}\n"
            f"   Resumen: {e.summary_es}\n"
            f"   Por que importa: {e.why_relevant}\n"
            f"   Que aprender: {e.what_to_learn}\n"
            f"   Fuente: {a.source} | {a.url}\n"
        )
    return "\n".join(lines)


def summarizer_node(state: NewsState) -> dict:
    selected = state.get("selected_articles", []) or []

    if not selected:
        return {
            "briefing": Briefing(
                headline=f"Briefing IA Personal - {date.today().isoformat()} (sin noticias relevantes)",
                tldr=[
                    "No se encontraron noticias con score de relevancia suficiente.",
                    "Considera ampliar las queries o el rango temporal en config.py.",
                    "El agente igual queda trazado en LangSmith para revision.",
                ],
                skill_of_the_day="Revisa tus SEARCH_QUERIES y prueba ampliar el time_range.",
            )
        }

    llm = init_chat_model(get_model()).with_structured_output(Briefing)
    user = SUMMARIZER_USER_TEMPLATE.format(
        articles_block=_format_articles_block(selected)
    )
    briefing: Briefing = llm.invoke(
        [
            {"role": "system", "content": SUMMARIZER_SYSTEM},
            {"role": "user", "content": user},
        ]
    )

    # Aseguramos que el headline tenga la fecha y maximo 3 bullets.
    today = date.today().isoformat()
    if today not in briefing.headline:
        briefing = Briefing(
            headline=f"{briefing.headline} - {today}",
            tldr=briefing.tldr[:3] if len(briefing.tldr) > 3 else briefing.tldr,
            skill_of_the_day=briefing.skill_of_the_day,
        )

    print(f"[summarizer] headline: {briefing.headline}")
    return {"briefing": briefing}
