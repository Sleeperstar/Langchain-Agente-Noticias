"""Researcher node: ejecuta varias queries en Tavily y devuelve articulos deduplicados."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_tavily import TavilySearch

from agente_noticias.config import SEARCH_QUERIES
from agente_noticias.schemas import Article
from agente_noticias.state import NewsState


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

    # Deduplicar por URL (manteniendo el primero, que suele ser el mas relevante).
    seen: set[str] = set()
    deduped: list[Article] = []
    for a in sorted(all_articles, key=lambda x: x.score, reverse=True):
        if not a.url or a.url in seen:
            continue
        seen.add(a.url)
        deduped.append(a)

    print(f"[researcher] {len(all_articles)} resultados -> {len(deduped)} unicos")
    return {"raw_articles": deduped}
