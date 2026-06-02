"""Researcher node: ejecuta varias queries en Tavily y devuelve articulos deduplicados."""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher

from langchain_tavily import TavilySearch

from agente_ia.config import SEARCH_QUERIES, TITLE_SIMILARITY_THRESHOLD
from agente_ia.schemas import Article
from agente_ia.state import NewsState

_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "new", "now", "is", "are", "el", "la", "los", "las", "un", "una", "de",
    "y", "o", "en", "con", "su", "que", "se",
}


def _normalize_title(title: str) -> str:
    """Normaliza un titulo para comparar: minusculas, sin puntuacion ni stopwords."""
    text = re.sub(r"[^\w\s]", " ", title.lower())
    tokens = [t for t in text.split() if t and t not in _STOPWORDS]
    return " ".join(tokens)


def _is_near_duplicate(norm_title: str, kept_norm_titles: list[str]) -> bool:
    """True si el titulo normalizado es muy similar a alguno ya conservado."""
    for other in kept_norm_titles:
        if not norm_title or not other:
            continue
        # Coincidencia por solapamiento de tokens o por ratio de similitud.
        ratio = SequenceMatcher(None, norm_title, other).ratio()
        if ratio >= TITLE_SIMILARITY_THRESHOLD:
            return True
        a, b = set(norm_title.split()), set(other.split())
        if a and b:
            overlap = len(a & b) / min(len(a), len(b))
            if overlap >= TITLE_SIMILARITY_THRESHOLD:
                return True
    return False


def _run_single_query(spec: dict) -> list[Article]:
    """Ejecuta una sola query Tavily y normaliza resultados."""
    params = {k: v for k, v in spec.items() if k != "query"}
    tool = TavilySearch(**params)
    raw = tool.invoke({"query": spec["query"]})

    out: list[Article] = []
    for item in raw.get("results", []) or []:
        out.append(
            Article(
                title=item.get("title", "").strip() or "(sin titulo)",
                url=item.get("url", ""),
                content=(item.get("content") or "")[:4000],
                source=item.get("url", "").split("/")[2] if item.get("url") else "",
                published_date=item.get("published_date", "") or "",
                score=float(item.get("score") or 0.0),
                query=spec["query"],
            )
        )
    return out


def researcher_node(state: NewsState) -> dict:
    """Lanza las queries en paralelo y deduplica por URL."""
    all_articles: list[Article] = []

    with ThreadPoolExecutor(max_workers=min(5, len(SEARCH_QUERIES))) as pool:
        futures = {pool.submit(_run_single_query, spec): spec for spec in SEARCH_QUERIES}
        for fut in as_completed(futures):
            try:
                all_articles.extend(fut.result())
            except Exception as exc:  # noqa: BLE001
                # No queremos que una query rota tumbe el grafo entero.
                spec = futures[fut]
                print(f"[researcher] query '{spec['query']}' fallo: {exc}")

    # Deduplicar: primero por URL exacta y luego por similitud de titulo
    # (manteniendo el de mayor score de Tavily, que solemos ver primero).
    seen_urls: set[str] = set()
    kept_norm_titles: list[str] = []
    deduped: list[Article] = []
    for a in sorted(all_articles, key=lambda x: x.score, reverse=True):
        if not a.url or a.url in seen_urls:
            continue
        norm = _normalize_title(a.title)
        if _is_near_duplicate(norm, kept_norm_titles):
            continue
        seen_urls.add(a.url)
        kept_norm_titles.append(norm)
        deduped.append(a)

    print(f"[researcher] {len(all_articles)} resultados -> {len(deduped)} unicos (URL + titulo)")
    return {"raw_articles": deduped}
