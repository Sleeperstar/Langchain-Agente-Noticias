"""Construccion del grafo LangGraph (flujo automatico, sin HITL).

Flujo:
    START -> researcher -> evaluator -> ranker -> summarizer -> email_writer
          -> outlook_sender -> END

Con `send=False` el grafo termina en `email_writer` (solo genera el preview,
util para `--dry-run`).
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agente_ia.config import get_recipient
from agente_ia.nodes.email_writer import email_writer_node
from agente_ia.nodes.evaluator import evaluator_node
from agente_ia.nodes.outlook_sender import outlook_sender_node
from agente_ia.nodes.ranker import ranker_node
from agente_ia.nodes.researcher import researcher_node
from agente_ia.nodes.summarizer import summarizer_node
from agente_ia.state import NewsState


def build_graph(checkpointer=None, send: bool = True):
    """Construye y compila el grafo.

    Args:
        checkpointer: opcional; el flujo es automatico y no requiere persistencia,
            pero se acepta por compatibilidad (p. ej. para usar threads/memoria).
        send: si es False, el grafo termina en `email_writer` y no envia el correo.
    """
    builder = StateGraph(NewsState)
    builder.add_node("researcher", researcher_node)
    builder.add_node("evaluator", evaluator_node)
    builder.add_node("ranker", ranker_node)
    builder.add_node("summarizer", summarizer_node)
    builder.add_node("email_writer", email_writer_node)

    builder.add_edge(START, "researcher")
    builder.add_edge("researcher", "evaluator")
    builder.add_edge("evaluator", "ranker")
    builder.add_edge("ranker", "summarizer")
    builder.add_edge("summarizer", "email_writer")

    if send:
        builder.add_node("outlook_sender", outlook_sender_node)
        builder.add_edge("email_writer", "outlook_sender")
        builder.add_edge("outlook_sender", END)
    else:
        builder.add_edge("email_writer", END)

    return builder.compile(checkpointer=checkpointer)


def default_config(thread_id: str = "agente-ia-personal-default") -> dict:
    """Config base con tags y metadata para que LangSmith etiquete el run."""
    from datetime import date

    return {
        "configurable": {"thread_id": thread_id},
        "tags": ["agente_ia_personal", "ai_news", date.today().isoformat()],
        "metadata": {
            "recipient": get_recipient(),
            "date": date.today().isoformat(),
        },
        "run_name": f"agente-ia-personal-{date.today().isoformat()}",
    }
