"""Evaluator node: el LLM puntua relevancia, asigna areas de impacto y resume."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain.chat_models import init_chat_model

from agente_noticias.config import (
    MAX_ARTICLES_IN_EMAIL,
    MIN_RELEVANCE_SCORE,
    get_model,
)
from agente_noticias.prompts import EVALUATOR_SYSTEM, EVALUATOR_USER_TEMPLATE
from agente_noticias.schemas import Article, ArticleEvaluation, EvaluatedArticle
from agente_noticias.state import NewsState


def _build_evaluator():
    """Devuelve un modelo configurado con structured output."""
    llm = init_chat_model(get_model())
    return llm.with_structured_output(ArticleEvaluation)


def _evaluate_one(article: Article) -> EvaluatedArticle | None:
    evaluator = _build_evaluator()
    user = EVALUATOR_USER_TEMPLATE.format(
        title=article.title,
        source=article.source,
        published_date=article.published_date,
        url=article.url,
        content=article.content[:3000],
    )
    try:
        evaluation: ArticleEvaluation = evaluator.invoke(
            [
                {"role": "system", "content": EVALUATOR_SYSTEM},
                {"role": "user", "content": user},
            ]
        )
        return EvaluatedArticle(article=article, evaluation=evaluation)
    except Exception as exc:  # noqa: BLE001
        print(f"[evaluator] fallo evaluando {article.url}: {exc}")
        return None


def evaluator_node(state: NewsState) -> dict:
    articles = state.get("raw_articles", []) or []
    if not articles:
        return {"scored_articles": [], "selected_articles": []}

    scored: list[EvaluatedArticle] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(_evaluate_one, a) for a in articles]
        for fut in as_completed(futures):
            result = fut.result()
            if result is not None:
                scored.append(result)

    # Filtrar y ordenar por relevancia.
    selected = [
        s for s in scored if s.evaluation.relevance_score >= MIN_RELEVANCE_SCORE
    ]
    selected.sort(key=lambda s: s.evaluation.relevance_score, reverse=True)
    selected = selected[:MAX_ARTICLES_IN_EMAIL]

    print(
        f"[evaluator] {len(scored)} evaluados, "
        f"{len(selected)} seleccionados (score>={MIN_RELEVANCE_SCORE})"
    )
    return {"scored_articles": scored, "selected_articles": selected}
