"""Construccion del grafo LangGraph (flujo semanal automatico, sin HITL).

Flujo:
    START -> researcher -> history_filter -> evaluator -> ranker
          -> [summarizer || card_images] -> email_writer -> outlook_sender
          -> persist_history -> END

- `history_filter` descarta noticias ya enviadas en semanas anteriores (SQLite local).
- `card_images` (en paralelo con `summarizer`) genera la imagen de cada tarjeta;
  `email_writer` espera a ambos.
- Con `send=False` (--dry-run) el grafo termina en `email_writer`: solo genera el
  preview, sin enviar ni persistir el historial.
- Guard: if fewer than MIN_ARTICLES_TO_SEND articles survive, `email_writer`
  routes to `no_articles` (send_ok=False, explicit send_result) and the run ends
  without `outlook_sender`/`persist_history`. The preview is still written.
"""
from __future__ import annotations

import sys

from langgraph.graph import END, START, StateGraph

from agente_noticias.config import MIN_ARTICLES_TO_SEND, get_recipient
from agente_noticias.nodes.card_images import card_images_node
from agente_noticias.nodes.email_writer import email_writer_node
from agente_noticias.nodes.evaluator import evaluator_node
from agente_noticias.nodes.history_filter import history_filter_node
from agente_noticias.nodes.outlook_sender import outlook_sender_node
from agente_noticias.nodes.persist_history import persist_history_node
from agente_noticias.nodes.ranker import ranker_node
from agente_noticias.nodes.researcher import researcher_node
from agente_noticias.nodes.summarizer import summarizer_node
from agente_noticias.state import NewsState

NO_ARTICLES_NODE = "no_articles"


def has_enough_articles(state: NewsState) -> bool:
    return len(state.get("selected_articles", []) or []) >= MIN_ARTICLES_TO_SEND


def no_articles_node(state: NewsState) -> dict:
    """Terminal node: never email an empty newsletter."""
    count = len(state.get("selected_articles", []) or [])
    reason = f"no se envio: {count} noticias seleccionadas (minimo {MIN_ARTICLES_TO_SEND})"
    print(f"[graph] ERROR: {reason}", file=sys.stderr)
    return {"send_result": reason, "send_ok": False}


def route_after_email_writer(state: NewsState, send: bool = True) -> str:
    """Next node after `email_writer`: send/finish, or stop on an empty selection."""
    if not has_enough_articles(state):
        return NO_ARTICLES_NODE
    return "outlook_sender" if send else END


def build_graph(checkpointer=None, send: bool = True):
    """Construye y compila el grafo.

    Args:
        checkpointer: opcional; el flujo es automatico y no requiere persistencia.
        send: si es False, el grafo termina en `email_writer` (solo preview).
    """
    builder = StateGraph(NewsState)
    builder.add_node("researcher", researcher_node)
    builder.add_node("history_filter", history_filter_node)
    builder.add_node("evaluator", evaluator_node)
    builder.add_node("ranker", ranker_node)
    builder.add_node("summarizer", summarizer_node)
    builder.add_node("card_images", card_images_node)
    builder.add_node("email_writer", email_writer_node)

    builder.add_edge(START, "researcher")
    builder.add_edge("researcher", "history_filter")
    builder.add_edge("history_filter", "evaluator")
    builder.add_edge("evaluator", "ranker")
    # Fan-out: text and card images are independent; fan-in at email_writer.
    builder.add_edge("ranker", "summarizer")
    builder.add_edge("ranker", "card_images")
    builder.add_edge(["summarizer", "card_images"], "email_writer")

    # Empty-newsletter guard (both modes): stop with send_ok=False.
    builder.add_node(NO_ARTICLES_NODE, no_articles_node)
    builder.add_edge(NO_ARTICLES_NODE, END)

    if send:
        builder.add_node("outlook_sender", outlook_sender_node)
        builder.add_node("persist_history", persist_history_node)
        builder.add_conditional_edges(
            "email_writer",
            lambda state: route_after_email_writer(state, send=True),
            ["outlook_sender", NO_ARTICLES_NODE],
        )
        builder.add_edge("outlook_sender", "persist_history")
        builder.add_edge("persist_history", END)
    else:
        builder.add_conditional_edges(
            "email_writer",
            lambda state: route_after_email_writer(state, send=False),
            [END, NO_ARTICLES_NODE],
        )

    return builder.compile(checkpointer=checkpointer)


def default_config(thread_id: str = "agente-noticias-default") -> dict:
    """Config base con tags y metadata para que LangSmith etiquete el run."""
    from datetime import date

    return {
        "configurable": {"thread_id": thread_id},
        "tags": ["agente_noticias", "win_ia_news", date.today().isoformat()],
        "metadata": {
            "recipient": get_recipient(),
            "date": date.today().isoformat(),
        },
        "run_name": f"agente-noticias-win-{date.today().isoformat()}",
    }
