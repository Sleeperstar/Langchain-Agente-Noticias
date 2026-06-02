"""History filter node: descarta noticias ya enviadas en semanas anteriores.

Consulta el historial en Supabase (ultimas DEDUP_WEEKS semanas) y quita de
`raw_articles` las noticias cuya URL o titulo sea muy similar a algo ya enviado.
Si no hay credenciales de Supabase, no filtra (degradacion segura).
"""
from __future__ import annotations

from agente_noticias.config import DEDUP_WEEKS
from agente_noticias.db import fetch_recent_sent
from agente_noticias.state import NewsState
from agente_noticias.text_utils import is_near_duplicate, normalize_title


def history_filter_node(state: NewsState) -> dict:
    articles = state.get("raw_articles", []) or []
    if not articles:
        return {"raw_articles": [], "dropped_by_history": 0}

    sent = fetch_recent_sent(DEDUP_WEEKS)
    if not sent:
        print("[history_filter] sin historial (o Supabase no configurado): no se filtra")
        return {"raw_articles": articles, "dropped_by_history": 0}

    sent_urls = {row.get("url", "") for row in sent if row.get("url")}
    sent_titles = [row.get("normalized_title", "") for row in sent if row.get("normalized_title")]

    kept = []
    dropped = 0
    for a in articles:
        norm = normalize_title(a.title)
        if a.url in sent_urls or is_near_duplicate(norm, sent_titles):
            dropped += 1
            continue
        kept.append(a)

    print(
        f"[history_filter] {len(articles)} -> {len(kept)} "
        f"({dropped} ya enviadas en las ultimas {DEDUP_WEEKS} semanas)"
    )
    return {"raw_articles": kept, "dropped_by_history": dropped}
