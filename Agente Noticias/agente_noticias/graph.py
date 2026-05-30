"""Construccion del grafo LangGraph con HITL antes del envio.

Flujo:
    START -> researcher -> evaluator -> summarizer -> email_writer
          -> approval_gate (interrupt) -> outlook_sender -> END

`approval_gate` usa `interrupt()` para pausar el grafo y esperar la decision
humana. Para reanudar, se invoca con `Command(resume=<bool|dict>)`.
"""
from __future__ import annotations

from typing import Literal

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agente_noticias.config import get_recipient
from agente_noticias.nodes.email_writer import email_writer_node
from agente_noticias.nodes.evaluator import evaluator_node
from agente_noticias.nodes.outlook_sender import outlook_sender_node
from agente_noticias.nodes.researcher import researcher_node
from agente_noticias.nodes.summarizer import summarizer_node
from agente_noticias.state import NewsState


def approval_gate(state: NewsState) -> Command[Literal["outlook_sender", "__end__"]]:
    """Pausa el grafo y espera la decision del humano.

    `interrupt()` devuelve lo que se pase en `Command(resume=...)`.

    - `True` -> aprobar y enviar
    - `False` -> rechazar y terminar
    - dict `{"approved": bool, "feedback": str}` -> aprobar con feedback opcional
    """
    decision = interrupt(
        {
            "action": "approve_email",
            "to": get_recipient(),
            "subject": state.get("subject", ""),
            "preview_path": state.get("preview_path", ""),
            "tldr": state["briefing"].tldr if state.get("briefing") else [],
            "article_count": len(state.get("selected_articles", []) or []),
            "message": (
                "Revisa output/preview.html y responde True (aprobar) o "
                "False (rechazar)."
            ),
        }
    )

    approved = False
    feedback = ""
    if isinstance(decision, bool):
        approved = decision
    elif isinstance(decision, dict):
        approved = bool(decision.get("approved", False))
        feedback = str(decision.get("feedback", ""))
    elif isinstance(decision, str):
        approved = decision.strip().lower() in {"s", "si", "sí", "y", "yes", "approve", "true"}

    if approved:
        return Command(
            update={"approved": True, "user_feedback": feedback},
            goto="outlook_sender",
        )
    return Command(
        update={"approved": False, "user_feedback": feedback, "send_result": "Rechazado por el usuario."},
        goto=END,
    )


def build_graph(checkpointer=None):
    """Construye y compila el grafo.

    Pasar siempre un checkpointer (por defecto InMemorySaver) porque el HITL
    via `interrupt()` requiere persistencia de estado entre invocaciones.
    """
    if checkpointer is None:
        checkpointer = InMemorySaver()

    builder = StateGraph(NewsState)
    builder.add_node("researcher", researcher_node)
    builder.add_node("evaluator", evaluator_node)
    builder.add_node("summarizer", summarizer_node)
    builder.add_node("email_writer", email_writer_node)
    builder.add_node("approval_gate", approval_gate)
    builder.add_node("outlook_sender", outlook_sender_node)

    builder.add_edge(START, "researcher")
    builder.add_edge("researcher", "evaluator")
    builder.add_edge("evaluator", "summarizer")
    builder.add_edge("summarizer", "email_writer")
    builder.add_edge("email_writer", "approval_gate")
    # approval_gate decide dinamicamente via Command(goto=...)
    builder.add_edge("outlook_sender", END)

    return builder.compile(checkpointer=checkpointer)


def default_config(thread_id: str = "agente-noticias-default") -> dict:
    """Config base con tags y metadata para que LangSmith etiquete el run."""
    from datetime import date

    return {
        "configurable": {"thread_id": thread_id},
        "tags": ["agente_noticias", "win_internet", date.today().isoformat()],
        "metadata": {
            "recipient": get_recipient(),
            "date": date.today().isoformat(),
        },
        "run_name": f"agente-noticias-{date.today().isoformat()}",
    }
