"""Ranker node: scoring comparativo de las candidatas.

A diferencia del evaluator (que puntua cada noticia por separado y tiende a
concentrar todo en 8-9), el ranker ve TODAS las candidatas juntas, colapsa
duplicados semanticos del mismo evento y asigna puntajes diferenciados,
reservando 10 solo para lo verdaderamente landmark.
"""
from __future__ import annotations

from typing import Callable

from agente_noticias.config import (
    MAX_ARTICLES,
    MAX_CANDIDATES,
    MIN_RELEVANCE_SCORE,
)
from agente_noticias.llm import get_chat_model
from agente_noticias.logo_finder import ensure_logo
from agente_noticias.logos import company_slug, display_name, is_key_company
from agente_noticias.prompts import RANKER_SYSTEM, RANKER_USER_TEMPLATE
from agente_noticias.schemas import EvaluatedArticle, Ranking
from agente_noticias.state import NewsState


def _company_label(company: str | None) -> str:
    if not company:
        return "-"
    name = display_name(company)
    return f"{name} [clave]" if is_key_company(company) else name


def _format_candidates_block(candidates: list[EvaluatedArticle]) -> str:
    lines = []
    for i, item in enumerate(candidates, start=1):
        a, e = item.article, item.evaluation
        lines.append(
            f"[{i}] ({e.relevance_score}/10 indep.) {a.title}\n"
            f"    Categoria: {e.category}\n"
            f"    Empresa: {_company_label(e.company)}\n"
            f"    Fuente: {a.source} | {a.url}\n"
            f"    Resumen: {e.summary_es}\n"
        )
    return "\n".join(lines)


def pick_diverse(
    ordered: list[EvaluatedArticle],
    pool: list[EvaluatedArticle],
    limit: int,
    accept: Callable[[EvaluatedArticle], bool] | None = None,
) -> list[EvaluatedArticle]:
    """At most one article per company, in `ordered` priority, topped up from `pool`.

    Companies are compared by `logos.company_slug` ("Google DeepMind" == "google").
    When topping up from `pool`, key-company articles go first (stable order otherwise).
    Articles without a company never collide. Only if there are not enough distinct
    companies do we fall back to repeating one, so the newsletter still has `limit` items.
    `accept` (e.g. "its company has a logo") is checked lazily, only for items that
    would otherwise be picked; rejected items are skipped in both passes.
    """
    pool = sorted(pool, key=lambda it: not is_key_company(it.evaluation.company))
    picked: list[EvaluatedArticle] = []
    companies: set[str] = set()
    seen: set[int] = set()
    for item in [*ordered, *pool]:
        if len(picked) >= limit:
            break
        slug = company_slug(item.evaluation.company)
        if id(item) in seen or (slug and slug in companies):
            continue
        seen.add(id(item))
        if accept is not None and not accept(item):
            continue
        picked.append(item)
        if slug:
            companies.add(slug)
    for item in [*ordered, *pool]:
        if len(picked) >= limit:
            break
        if id(item) not in seen:
            seen.add(id(item))
            if accept is not None and not accept(item):
                continue
            picked.append(item)
            print(f"[ranker] sin empresas suficientes: repito {item.evaluation.company}")
    return picked


def _has_logo(item: EvaluatedArticle) -> bool:
    """True if the card can carry a logo badge (built-in, learned, or found now)."""
    company = item.evaluation.company
    if company and ensure_logo(company) is not None:
        return True
    print(f"[ranker] descarto '{item.article.title[:60]}': sin logo para {company or '-'}")
    return False


def ranker_node(state: NewsState) -> dict:
    scored = state.get("scored_articles", []) or []
    if not scored:
        return {"selected_articles": []}

    # Candidatos: los mejores por score independiente (desempate con score de Tavily).
    # Solo noticias con una empresa protagonista: cada tarjeta lleva su logo.
    candidates = [
        s for s in scored
        if s.evaluation.relevance_score >= MIN_RELEVANCE_SCORE and s.evaluation.company
    ]
    candidates.sort(
        key=lambda s: (s.evaluation.relevance_score, s.article.score),
        reverse=True,
    )
    candidates = candidates[:MAX_CANDIDATES]

    if not candidates:
        return {"selected_articles": []}

    llm = get_chat_model().with_structured_output(Ranking)
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
        # Candidates go in as the pool so key companies keep their priority.
        return {"selected_articles": pick_diverse([], candidates, MAX_ARTICLES, _has_logo)}

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

    # Enforce variety even if the model ignored the one-per-company rule.
    # and only keep stories whose company logo exists (or the logo agent can find it).
    selected = pick_diverse(selected, candidates, MAX_ARTICLES, _has_logo)

    print(
        f"[ranker] {len(candidates)} candidatas -> {len(selected)} seleccionadas "
        f"(scores diferenciados)"
    )
    return {"selected_articles": selected}
