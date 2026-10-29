"""Evaluator node: el LLM puntua relevancia, asigna categoria y resume.

Solo puntua cada noticia de forma independiente. La seleccion final y la
diferenciacion de scores las hace el nodo `ranker`.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

from agente_noticias._concurrency import submit_with_context
from agente_noticias.config import get_eval_model
from agente_noticias.llm import get_chat_model
from agente_noticias.prompts import EVALUATOR_SYSTEM, EVALUATOR_USER_TEMPLATE
from agente_noticias.schemas import Article, ArticleEvaluation, EvaluatedArticle
from agente_noticias.state import NewsState


def _build_evaluator():
    """Devuelve un modelo configurado con structured output."""
    return get_chat_model(get_eval_model()).with_structured_output(ArticleEvaluation)


def _evaluate_one_or_error(article: Article) -> tuple[EvaluatedArticle | None, Exception | None]:
    """Evaluates `article`: (result, None) or (None, error) when the LLM call fails.

    Building the model stays outside the try so configuration errors (e.g. a
    missing OPENROUTER_API_KEY) fail fast instead of being logged per article.
    """
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
        return EvaluatedArticle(article=article, evaluation=evaluation), None
    except Exception as exc:  # noqa: BLE001
        print(f"[evaluator] fallo evaluando {article.url}: {exc}")
        return None, exc


def _evaluate_one(article: Article) -> EvaluatedArticle | None:
    return _evaluate_one_or_error(article)[0]


def evaluator_node(state: NewsState) -> dict:
    articles = state.get("raw_articles", []) or []
    if not articles:
        return {"scored_articles": []}

    scored: list[EvaluatedArticle] = []
    errors: list[Exception] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [submit_with_context(pool, _evaluate_one_or_error, a) for a in articles]
        for fut in as_completed(futures):
            result, error = fut.result()
            if result is not None:
                scored.append(result)
            if error is not None:
                errors.append(error)

    if not scored and errors:
        # One clear summary line on top of the per-article noise (e.g. quota/auth).
        first = errors[0]
        print(
            f"[evaluator] ERROR: fallaron las {len(errors)} evaluaciones; "
            f"primer error: {type(first).__name__}: {first}",
            file=sys.stderr,
        )
    print(f"[evaluator] {len(scored)} noticias evaluadas")
    return {"scored_articles": scored}
