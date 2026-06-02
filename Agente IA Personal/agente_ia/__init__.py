"""Agente IA Personal - paquete principal.

Importar este paquete dispara la carga del entorno (.env) y activa el
tracing de LangSmith antes de construir el grafo.
"""

from agente_ia.config import load_environment

load_environment()

__all__ = ["load_environment"]
