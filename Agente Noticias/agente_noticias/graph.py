"""Construccion del grafo LangGraph (flujo semanal automatico, sin HITL).

Flujo:
    START -> researcher -> history_filter -> evaluator -> ranker -> summarizer
          -> email_writer -> outlook_sender -> persist_history -> END

- `history_filter` descarta noticias ya enviadas en semanas anteriores (Supabase).
- Con `send=False` (--dry-run) el grafo termina en `email_writer`: solo genera el
  preview, sin enviar ni persistir el historial.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agente_noticias.config import get_recipient
from agente_noticias.nodes.email_writer import email_writer_node
from agente_noticias.nodes.evaluator import evaluator_node
from agente_noticias.nodes.history_filter import history_filter_node
from agente_noticias.nodes.outlook_sender import outlook_sender_node
from agente_noticias.nodes.persist_history import persist_history_node
from agente_noticias.nodes.ranker import ranker_node
from agente_noticias.nodes.researcher import researcher_node
from agente_noticias.nodes.summarizer import summarizer_node
from agente_noticias.state import NewsState


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
    builder.add_node("email_writer", email_writer_node)

    builder.add_edge(START, "researcher")
    builder.add_edge("researcher", "history_filter")
    builder.add_edge("history_filter", "evaluator")
    builder.add_edge("evaluator", "ranker")
    builder.add_edge("ranker", "summarizer")
    builder.add_edge("summarizer", "email_writer")

    if send:
        builder.add_node("outlook_sender", outlook_sender_node)
        builder.add_node("persist_history", persist_history_node)
        builder.add_edge("email_writer", "outlook_sender")
        builder.add_edge("outlook_sender", "persist_history")
        builder.add_edge("persist_history", END)
    else:
        builder.add_edge("email_writer", END)

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
