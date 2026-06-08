"""Generacion y anti-repeticion del chiste del briefing."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from langchain.chat_models import init_chat_model

from agente_noticias.config import DEDUP_WEEKS, get_model
from agente_noticias.db import fetch_recent_jokes
from agente_noticias.prompts import JOKE_SYSTEM, JOKE_USER_TEMPLATE
from agente_noticias.schemas import JokeOut

# Umbral de similitud para considerar que un chiste se repite (0-1).
JOKE_SIMILARITY_THRESHOLD = 0.6


def normalize_joke(text: str) -> str:
    """Normaliza un chiste para comparar: minusculas y sin puntuacion."""
    return re.sub(r"[^\w\s]", " ", (text or "").lower()).strip()


def is_joke_repeated(joke: str, recent: list[str]) -> bool:
    """True si el chiste es muy parecido a alguno ya usado."""
    norm = normalize_joke(joke)
    if not norm:
        return False
    for other in recent:
        other_norm = normalize_joke(other)
        if not other_norm:
            continue
        if SequenceMatcher(None, norm, other_norm).ratio() >= JOKE_SIMILARITY_THRESHOLD:
            return True
    return False


def recent_jokes_block(jokes: list[str]) -> str:
    """Formatea los chistes recientes para inyectarlos en un prompt."""
    if not jokes:
        return "(ninguno todavia)"
    return "\n".join(f"- {j}" for j in jokes)


def get_recent_jokes(weeks: int | None = None) -> list[str]:
    """Lee de Supabase los chistes usados recientemente."""
    return fetch_recent_jokes(weeks if weeks is not None else DEDUP_WEEKS)


def generate_unique_joke(
    recent: list[str] | None = None,
    avoid: list[str] | None = None,
    max_attempts: int = 3,
) -> str:
    """Genera un chiste nuevo evitando los recientes (y los de `avoid`)."""
    recent = recent if recent is not None else get_recent_jokes()
    blocked = list(recent) + list(avoid or [])

    llm = init_chat_model(get_model()).with_structured_output(JokeOut)
    last = ""
    for _ in range(max_attempts):
        try:
            out: JokeOut = llm.invoke(
                [
                    {"role": "system", "content": JOKE_SYSTEM},
                    {"role": "user", "content": JOKE_USER_TEMPLATE.format(
                        recent_jokes_block=recent_jokes_block(blocked)
                    )},
                ]
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[jokes] fallo generando chiste: {exc}")
            break
        last = out.chiste.strip()
        if last and not is_joke_repeated(last, blocked):
            return last
        # Si se repitio, lo agregamos a la lista a evitar y reintentamos.
        if last:
            blocked.append(last)
    return last
