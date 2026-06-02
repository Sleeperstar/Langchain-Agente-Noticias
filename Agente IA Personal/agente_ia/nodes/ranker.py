"""Ranker node: scoring comparativo de las candidatas.

A diferencia del evaluator (que puntua cada noticia por separado y tiende a
concentrar todo en 8-9), el ranker ve TODAS las candidatas juntas, colapsa
duplicados semanticos del mismo evento y asigna puntajes diferenciados,
reservando 10 solo para lo verdaderamente landmark.
"""
from __future__ import annotations

from langchain.chat_models import init_chat_model

from agente_ia.config import MAX_ARTICLES, MAX_CANDIDATES, MIN_RELEVANCE_SCORE, get_model
from agente_ia.prompts import RANKER_SYSTEM, RANKER_USER_TEMPLATE
from agente_ia.schemas import EvaluatedArticle, Ranking
from agente_ia.state import NewsState


def _format_candidates_block(candidates: list[EvaluatedArticle]) -> str:
    lines = []
    for i, item in enumerate(candidates, start=1):
        a, e = item.article, item.evaluation
        lines.append(
            f"[{i}] ({e.relevance_score}/10 indep.) {a.title}\n"
            f"    Categoria: {e.category}\n"
            f"    Fuente: {a.source} | {a.url}\n"
            f"    Resumen: {e.summary_es}\n"
        )
    return "\n".join(lines)


def ranker_node(state: NewsState) -> dict:
    scored = state.get("scored_articles", []) or []
    if not scored:
        return {"selected_articles": []}

    # Candidatos: los mejores por score independiente (desempate con score de Tavily).
    candidates = [
        s for s in scored if s.evaluation.relevance_score >= MIN_RELEVANCE_SCORE
    ]
    candidates.sort(
        key=lambda s: (s.evaluation.relevance_score, s.article.score),
        reverse=True,
    )
    candidates = candidates[:MAX_CANDIDATES]

    if not candidates:
        return {"selected_articles": []}

    llm = init_chat_model(get_model()).with_structured_output(Ranking)
    user = RANKER_USER_TEMPLATE.format(
        candidates_block=_format_candidates_block(candidates),
        max_articles=MAX_ARTICLES,
    )

    try:
        ranking: Ranking = llm.invoke(
            [
                {"role": "system", "content": RANKER_SYSTEM.format(max_articles=MAX_ARTICLES)},
                {"role": "user", "content": user},
            ]
        )
    except Exception as exc:  # noqa: BLE001
        # Fallback: si el ranker falla, devolvemos el top por score independiente.
        print(f"[ranker] fallo, uso fallback por score independiente: {exc}")
        return {"selected_articles": candidates[:MAX_ARTICLES]}

    selected: list[EvaluatedArticle] = []
    used_indices: set[int] = set()
    for sel in ranking.selected:
        idx = sel.index - 1  # 1-based -> 0-based
        if idx < 0 or idx >= len(candidates) or idx in used_indices:
            continue
        used_indices.add(idx)
        item = candidates[idx]
        # Sobrescribimos el score con el comparativo (diferenciado) del ranker.
        item.evaluation.relevance_score = sel.final_score
        selected.append(item)
        if len(selected) >= MAX_ARTICLES:
            break

    # Si el ranker devolvio menos de lo esperado, completamos con el resto.
    if not selected:
        selected = candidates[:MAX_ARTICLES]

    print(f"[ranker] {len(candidates)} candidatas -> {len(selected)} seleccionadas (scores diferenciados)")
    return {"selected_articles": selected}
