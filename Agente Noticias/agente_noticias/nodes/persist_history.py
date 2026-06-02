"""Persist history node: guarda en Supabase las noticias enviadas.

Solo persiste si el correo se envio correctamente. Asi la proxima corrida no
repite estas noticias. Degrada de forma segura si Supabase no esta configurado.
"""
from __future__ import annotations

import os

from agente_noticias.config import DEFAULT_PROJECT, get_recipients
from agente_noticias.db import save_briefing
from agente_noticias.state import NewsState
from agente_noticias.text_utils import normalize_title


def persist_history_node(state: NewsState) -> dict:
    send_result = state.get("send_result", "") or ""
    selected = state.get("selected_articles", []) or []

    # Solo persistimos si hubo envio exitoso.
    if "enviado" not in send_result.lower():
        print("[persist_history] no se envio el correo, no se guarda historial")
        return {}

    if not selected:
        return {}

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
            }
        )

    briefing_id = save_briefing(
        subject=state.get("subject", ""),
        recipients=", ".join(get_recipients()),
        run_id=state.get("run_id", ""),
        langsmith_project=os.getenv("LANGSMITH_PROJECT", DEFAULT_PROJECT),
        articles=articles,
    )

    if briefing_id:
        print(f"[persist_history] historial guardado (briefing_id={briefing_id})")
    else:
        print("[persist_history] no se guardo historial (Supabase no configurado o error)")

    return {"briefing_id": briefing_id}
