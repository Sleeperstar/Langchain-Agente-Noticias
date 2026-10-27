"""Persist history node: guarda en el historial SQLite las noticias enviadas.

Solo persiste si el correo se envio correctamente. Asi la proxima corrida no
repite estas noticias. Degrada de forma segura si la BD falla.
"""
from __future__ import annotations

import os

from agente_noticias.concepts import normalize_concept
from agente_noticias.config import DEFAULT_PROJECT, get_recipients
from agente_noticias.db import save_briefing
from agente_noticias.jokes import normalize_joke
from agente_noticias.logos import company_slug
from agente_noticias.nodes.card_images import project_relative
from agente_noticias.schemas import Briefing, EvaluatedArticle
from agente_noticias.state import NewsState
from agente_noticias.text_utils import normalize_title


def history_payload(selected: list[EvaluatedArticle], briefing: Briefing | None) -> dict:
    """`save_briefing` keyword arguments derived from the newsletter content.

    Returns `articles` plus the joke/concept fields. Shared with the send-ready
    draft (agente_noticias.draft) so both paths persist identical history rows.
    """
    articles = []
    for item in selected:
        a, e = item.article, item.evaluation
        articles.append(
            {
                "url": a.url,
                "normalized_title": normalize_title(a.title),
                "title": a.title,
                "source": a.source,
                "category": e.category,
                "relevance_score": e.relevance_score,
                "published_date": a.published_date,
                "company": company_slug(e.company),
                "image_path": project_relative(item.card_image_path),
            }
        )

    joke = getattr(briefing, "chiste", "") if briefing is not None else ""
    concepto_titulo = getattr(briefing, "concepto_titulo", "") if briefing is not None else ""
    concepto_explicacion = (
        getattr(briefing, "concepto_explicacion", "") if briefing is not None else ""
    )
    return {
        "articles": articles,
        "joke": joke,
        "joke_normalized": normalize_joke(joke),
        "concepto_titulo": concepto_titulo,
        "concepto_explicacion": concepto_explicacion,
        "concepto_normalized": normalize_concept(concepto_titulo),
    }


def persist_history_node(state: NewsState) -> dict:
    selected = state.get("selected_articles", []) or []

    # Solo persistimos si hubo envio exitoso (flag explicito de outlook_sender).
    if state.get("send_ok") is not True:
        print("[persist_history] no se envio el correo, no se guarda historial")
        return {}

    if not selected:
        return {}

    payload = history_payload(selected, state.get("briefing"))

    briefing_id = save_briefing(
        subject=state.get("subject", ""),
        recipients=", ".join(get_recipients()),
        run_id=state.get("run_id", ""),
        langsmith_project=os.getenv("LANGSMITH_PROJECT", DEFAULT_PROJECT),
        **payload,
    )

    if briefing_id:
        print(f"[persist_history] historial guardado (briefing_id={briefing_id})")
    else:
        print("[persist_history] no se guardo historial (error en la BD, ver [db] WARNING)")

    return {"briefing_id": briefing_id}
