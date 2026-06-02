"""Entry-point para LangGraph Studio / langgraph dev.

LangGraph Studio inyecta su propio checkpointer, por eso aqui compilamos
sin checkpointer. Incluye el flujo completo (con envio por Outlook y persistencia)
para poder ver todos los estados del grafo en Studio.
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

import agente_noticias  # noqa: F401  -> carga .env y activa LangSmith
from agente_noticias.nodes.email_writer import email_writer_node
from agente_noticias.nodes.evaluator import evaluator_node
from agente_noticias.nodes.history_filter import history_filter_node
from agente_noticias.nodes.outlook_sender import outlook_sender_node
from agente_noticias.nodes.persist_history import persist_history_node
from agente_noticias.nodes.ranker import ranker_node
from agente_noticias.nodes.researcher import researcher_node
from agente_noticias.nodes.summarizer import summarizer_node
from agente_noticias.state import NewsState

_builder = StateGraph(NewsState)
_builder.add_node("researcher", researcher_node)
_builder.add_node("history_filter", history_filter_node)
_builder.add_node("evaluator", evaluator_node)
_builder.add_node("ranker", ranker_node)
_builder.add_node("summarizer", summarizer_node)
_builder.add_node("email_writer", email_writer_node)
_builder.add_node("outlook_sender", outlook_sender_node)
_builder.add_node("persist_history", persist_history_node)

_builder.add_edge(START, "researcher")
_builder.add_edge("researcher", "history_filter")
_builder.add_edge("history_filter", "evaluator")
_builder.add_edge("evaluator", "ranker")
_builder.add_edge("ranker", "summarizer")
_builder.add_edge("summarizer", "email_writer")
_builder.add_edge("email_writer", "outlook_sender")
_builder.add_edge("outlook_sender", "persist_history")
_builder.add_edge("persist_history", END)

graph = _builder.compile()
