"""Utilidades de concurrencia que preservan el contexto de LangSmith.

Cuando paralelizamos llamadas (evaluator, researcher) con ThreadPoolExecutor, los
hilos NO heredan los contextvars del hilo padre. LangChain/LangSmith guardan el
"run tree" activo en un contextvar, asi que sin propagarlo las llamadas LLM/tool
de los hilos se registran como trazas SUELTAS (orphans) en vez de anidarse bajo la
corrida del grafo. Copiamos el contexto para que todo quede en UNA sola traza.
"""
from __future__ import annotations

import contextvars
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, TypeVar

T = TypeVar("T")


def submit_with_context(pool: ThreadPoolExecutor, fn: Callable[..., T], *args, **kwargs) -> "Future[T]":
    """Igual que pool.submit pero ejecutando con una copia del contexto actual."""
    ctx = contextvars.copy_context()
    return pool.submit(ctx.run, lambda: fn(*args, **kwargs))
