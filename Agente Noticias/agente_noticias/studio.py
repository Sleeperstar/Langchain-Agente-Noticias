"""Entry-point para LangGraph Studio / langgraph dev.

LangGraph Studio inyecta su propio checkpointer, por eso aqui compilamos
SIN checkpointer (a diferencia de `build_graph()` que usa InMemorySaver
para que el HITL funcione en el script CLI / notebook).
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

import agente_noticias  # noqa: F401  -> carga .env y activa LangSmith
from agente_noticias.graph import approval_gate
from agente_noticias.nodes.email_writer import email_writer_node
from agente_noticias.nodes.evaluator import evaluator_node
from agente_noticias.nodes.outlook_sender import outlook_sender_node
from agente_noticias.nodes.researcher import researcher_node
from agente_noticias.nodes.summarizer import summarizer_node
from agente_noticias.state import NewsState

_builder = StateGraph(NewsState)
_builder.add_node("researcher", researcher_node)
_builder.add_node("evaluator", evaluator_node)
_builder.add_node("summarizer", summarizer_node)
_builder.add_node("email_writer", email_writer_node)
_builder.add_node("approval_gate", approval_gate)
_builder.add_node("outlook_sender", outlook_sender_node)

_builder.add_edge(START, "researcher")
_builder.add_edge("researcher", "evaluator")
_builder.add_edge("evaluator", "summarizer")
_builder.add_edge("summarizer", "email_writer")
_builder.add_edge("email_writer", "approval_gate")
_builder.add_edge("outlook_sender", END)

graph = _builder.compile()
