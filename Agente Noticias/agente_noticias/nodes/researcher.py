"""Researcher node: ejecuta varias queries en Tavily y devuelve articulos deduplicados."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_tavily import TavilySearch

from agente_noticias._concurrency import submit_with_context
from agente_noticias.config import SEARCH_QUERIES
from agente_noticias.schemas import Article
from agente_noticias.state import NewsState
from agente_noticias.text_utils import is_near_duplicate, normalize_title


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
    """Lanza las queries en paralelo y deduplica por URL y por titulo similar."""
    all_articles: list[Article] = []

    with ThreadPoolExecutor(max_workers=min(5, len(SEARCH_QUERIES))) as pool:
        futures = {
            submit_with_context(pool, _run_single_query, spec): spec
            for spec in SEARCH_QUERIES
        }
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
        norm = normalize_title(a.title)
        if is_near_duplicate(norm, kept_norm_titles):
            continue
        seen_urls.add(a.url)
        kept_norm_titles.append(norm)
        deduped.append(a)

    print(f"[researcher] {len(all_articles)} resultados -> {len(deduped)} unicos (URL + titulo)")
    return {"raw_articles": deduped}
