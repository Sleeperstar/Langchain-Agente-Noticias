"""Generacion y anti-repeticion del 'concepto del dia'."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from langchain.chat_models import init_chat_model

from agente_noticias.config import DEDUP_WEEKS, get_model
from agente_noticias.db import fetch_recent_concepts
from agente_noticias.prompts import (
    CONCEPT_FREE_INSTRUCTION,
    CONCEPT_SYSTEM,
    CONCEPT_TOPIC_INSTRUCTION,
    CONCEPT_USER_TEMPLATE,
)
from agente_noticias.schemas import ConceptOut

# Umbral de similitud para considerar que un concepto se repite (0-1).
CONCEPT_SIMILARITY_THRESHOLD = 0.7


def normalize_concept(text: str) -> str:
    """Normaliza un titulo de concepto para comparar."""
    t = re.sub(r"[^\w\s]", " ", (text or "").lower())
    # Quitamos muletillas tipicas para comparar el nucleo del concepto.
    for stop in ("que es", "que son", "como funciona", "el ", "la ", "los ", "las ", "un ", "una "):
        t = t.replace(stop, " ")
    return re.sub(r"\s+", " ", t).strip()


def is_concept_repeated(titulo: str, recent: list[str]) -> bool:
    norm = normalize_concept(titulo)
    if not norm:
        return False
    for other in recent:
        other_norm = normalize_concept(other)
        if not other_norm:
            continue
        if norm == other_norm:
            return True
        if SequenceMatcher(None, norm, other_norm).ratio() >= CONCEPT_SIMILARITY_THRESHOLD:
            return True
    return False


def recent_concepts_block(concepts: list[str]) -> str:
    if not concepts:
        return "(ninguno todavia)"
    return "\n".join(f"- {c}" for c in concepts)


def get_recent_concepts(weeks: int | None = None) -> list[str]:
    return fetch_recent_concepts(weeks if weeks is not None else DEDUP_WEEKS)


def generate_concept(
    recent: list[str] | None = None,
    avoid: list[str] | None = None,
    topic: str | None = None,
    news_context: str = "",
    max_attempts: int = 3,
) -> ConceptOut | None:
    """Genera un concepto del dia. Si `topic` viene, lo explica; si no, elige uno nuevo.

    Evita repetir los conceptos recientes (y los de `avoid`). Si el usuario pide un
    tema explicito, no forzamos la deduplicacion (respetamos su pedido).
    """
    recent = recent if recent is not None else get_recent_concepts()
    blocked = list(recent) + list(avoid or [])
    topic = (topic or "").strip()

    instruction = (
        CONCEPT_TOPIC_INSTRUCTION.format(topic=topic) if topic else CONCEPT_FREE_INSTRUCTION
    )

    llm = init_chat_model(get_model()).with_structured_output(ConceptOut)
    last: ConceptOut | None = None
    for _ in range(max_attempts):
        try:
            out: ConceptOut = llm.invoke(
                [
                    {"role": "system", "content": CONCEPT_SYSTEM},
                    {"role": "user", "content": CONCEPT_USER_TEMPLATE.format(
                        news_context=news_context or "(sin contexto)",
                        recent_concepts_block=recent_concepts_block(blocked),
                        topic_instruction=instruction,
                    )},
                ]
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[concepts] fallo generando concepto: {exc}")
            break
        last = out
        # Si el usuario pidio un tema explicito, no rechazamos por similitud.
        if topic or not is_concept_repeated(out.concepto_titulo, blocked):
            return out
        blocked.append(out.concepto_titulo)
    return last
