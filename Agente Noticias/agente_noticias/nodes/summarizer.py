"""Summarizer node: produce headline + TL;DR + concepto del dia + chiste."""
from __future__ import annotations

from datetime import date

from langchain.chat_models import init_chat_model

from agente_noticias.concepts import (
    generate_concept,
    get_recent_concepts,
    is_concept_repeated,
    recent_concepts_block,
)
from agente_noticias.config import get_model
from agente_noticias.jokes import (
    generate_unique_joke,
    get_recent_jokes,
    is_joke_repeated,
    recent_jokes_block,
)
from agente_noticias.prompts import SUMMARIZER_SYSTEM, SUMMARIZER_USER_TEMPLATE
from agente_noticias.schemas import Briefing
from agente_noticias.state import NewsState


def _format_articles_block(selected) -> str:
    lines = []
    for i, item in enumerate(selected, start=1):
        a, e = item.article, item.evaluation
        lines.append(
            f"{i}. [{e.relevance_score}/10] {a.title}\n"
            f"   Categoria: {e.category}\n"
            f"   Resumen: {e.summary_es}\n"
            f"   En simple: {e.en_simple}\n"
            f"   Fuente: {a.source} | {a.url}\n"
        )
    return "\n".join(lines)


def summarizer_node(state: NewsState) -> dict:
    selected = state.get("selected_articles", []) or []

    if not selected:
        return {
            "briefing": Briefing(
                headline=f"Briefing IA Win - {date.today().isoformat()} (sin noticias relevantes)",
                tldr=[
                    "No se encontraron noticias con score de relevancia suficiente.",
                    "Considera ampliar las queries o el rango temporal en config.py.",
                    "El agente igual queda trazado en LangSmith para revision.",
                ],
                concepto_titulo="",
                concepto_explicacion="",
                chiste="",
            )
        }

    recent_jokes = get_recent_jokes()
    recent_concepts = get_recent_concepts()

    llm = init_chat_model(get_model()).with_structured_output(Briefing)
    user = SUMMARIZER_USER_TEMPLATE.format(
        articles_block=_format_articles_block(selected),
        recent_concepts_block=recent_concepts_block(recent_concepts),
        recent_jokes_block=recent_jokes_block(recent_jokes),
    )
    briefing: Briefing = llm.invoke(
        [
            {"role": "system", "content": SUMMARIZER_SYSTEM},
            {"role": "user", "content": user},
        ]
    )

    # Si el chiste se parece a uno ya enviado, generamos uno nuevo.
    chiste = briefing.chiste
    if is_joke_repeated(chiste, recent_jokes):
        print("[summarizer] chiste repetido, generando uno nuevo")
        chiste = generate_unique_joke(recent=recent_jokes, avoid=[chiste])

    # Si el concepto del dia se repite, generamos uno distinto.
    concepto_titulo = briefing.concepto_titulo
    concepto_explicacion = briefing.concepto_explicacion
    if is_concept_repeated(concepto_titulo, recent_concepts):
        print("[summarizer] concepto repetido, generando uno nuevo")
        nuevo = generate_concept(recent=recent_concepts, avoid=[concepto_titulo])
        if nuevo is not None:
            concepto_titulo = nuevo.concepto_titulo
            concepto_explicacion = nuevo.concepto_explicacion

    # Aseguramos que el headline tenga la fecha y maximo 3 bullets.
    today = date.today().isoformat()
    needs_date = today not in briefing.headline
    briefing = Briefing(
        headline=f"{briefing.headline} - {today}" if needs_date else briefing.headline,
        tldr=briefing.tldr[:3] if len(briefing.tldr) > 3 else briefing.tldr,
        concepto_titulo=concepto_titulo,
        concepto_explicacion=concepto_explicacion,
        chiste=chiste,
    )

    print(f"[summarizer] headline: {briefing.headline}")
    return {"briefing": briefing}
