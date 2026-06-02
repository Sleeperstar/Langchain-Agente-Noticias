"""Entry-point para LangGraph Studio / langgraph dev.

LangGraph Studio inyecta su propio checkpointer, por eso aqui compilamos
sin checkpointer. Incluimos el flujo completo (con envio por Outlook).
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

import agente_ia  # noqa: F401  -> carga .env y activa LangSmith
from agente_ia.nodes.email_writer import email_writer_node
from agente_ia.nodes.evaluator import evaluator_node
from agente_ia.nodes.outlook_sender import outlook_sender_node
from agente_ia.nodes.ranker import ranker_node
from agente_ia.nodes.researcher import researcher_node
from agente_ia.nodes.summarizer import summarizer_node
from agente_ia.state import NewsState

_builder = StateGraph(NewsState)
_builder.add_node("researcher", researcher_node)
_builder.add_node("evaluator", evaluator_node)
_builder.add_node("ranker", ranker_node)
_builder.add_node("summarizer", summarizer_node)
_builder.add_node("email_writer", email_writer_node)
_builder.add_node("outlook_sender", outlook_sender_node)

_builder.add_edge(START, "researcher")
_builder.add_edge("researcher", "evaluator")
_builder.add_edge("evaluator", "ranker")
_builder.add_edge("ranker", "summarizer")
_builder.add_edge("summarizer", "email_writer")
_builder.add_edge("email_writer", "outlook_sender")
_builder.add_edge("outlook_sender", END)

graph = _builder.compile()
