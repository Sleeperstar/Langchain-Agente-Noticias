"""Entry-point para LangGraph Studio / langgraph dev.

LangGraph Studio inyecta su propio checkpointer, por eso aqui compilamos
sin checkpointer. Incluye el flujo completo (con envio por Outlook y persistencia)
para poder ver todos los estados del grafo en Studio. Reutiliza `build_graph` para
heredar el mismo flujo (tarjetas, guard de boletin vacio) que `scripts/run.py`.
"""
from __future__ import annotations

import agente_noticias  # noqa: F401  -> carga .env y activa LangSmith
from agente_noticias.graph import build_graph

graph = build_graph(send=True)
