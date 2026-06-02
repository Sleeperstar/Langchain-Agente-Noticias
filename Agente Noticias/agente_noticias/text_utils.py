"""Utilidades de texto para deduplicar noticias por titulo."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from agente_noticias.config import TITLE_SIMILARITY_THRESHOLD

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "new", "now", "is", "are", "el", "la", "los", "las", "un", "una", "de",
    "y", "o", "en", "con", "su", "que", "se",
}


def normalize_title(title: str) -> str:
    """Normaliza un titulo para comparar: minusculas, sin puntuacion ni stopwords."""
    text = re.sub(r"[^\w\s]", " ", (title or "").lower())
    tokens = [t for t in text.split() if t and t not in _STOPWORDS]
    return " ".join(tokens)


def is_near_duplicate(
    norm_title: str,
    kept_norm_titles: list[str],
    threshold: float = TITLE_SIMILARITY_THRESHOLD,
) -> bool:
    """True si el titulo normalizado es muy similar a alguno de la lista dada."""
    for other in kept_norm_titles:
        if not norm_title or not other:
            continue
        ratio = SequenceMatcher(None, norm_title, other).ratio()
        if ratio >= threshold:
            return True
        a, b = set(norm_title.split()), set(other.split())
        if a and b:
            overlap = len(a & b) / min(len(a), len(b))
            if overlap >= threshold:
                return True
    return False
