"""Ranker variety: at most one news item per company."""
from __future__ import annotations

from agente_noticias.nodes import ranker
from agente_noticias.schemas import Article, ArticleEvaluation, EvaluatedArticle, Ranking


def _item(n: int, company: str | None, score: int = 8) -> EvaluatedArticle:
    return EvaluatedArticle(
        article=Article(title=f"News {n}", url=f"https://example.com/{n}"),
        evaluation=ArticleEvaluation(
            reasoning="r",
            relevance_score=score,
            category="Nuevos modelos",
            company=company,
            label_es="Lanzamiento",
            title_es=f"Noticia {n}",
            summary_es="Resumen. Gancho.",
        ),
    )


def _titles(items):
    return [it.article.title for it in items]


def test_pick_diverse_keeps_one_per_company_and_tops_up_from_pool():
    a, b, c = _item(1, "openai"), _item(2, "openai"), _item(3, "openai")
    d, e = _item(4, "google"), _item(5, None)
    picked = ranker.pick_diverse([a, b, c], [a, b, c, d, e], 3)
    assert _titles(picked) == ["News 1", "News 4", "News 5"]


def test_pick_diverse_items_without_company_never_collide():
    items = [_item(1, None), _item(2, None), _item(3, None)]
    assert _titles(ranker.pick_diverse(items, [], 3)) == ["News 1", "News 2", "News 3"]


def test_pick_diverse_repeats_company_only_when_nothing_else_is_left(capsys):
    items = [_item(1, "openai"), _item(2, "openai"), _item(3, "meta")]
    picked = ranker.pick_diverse(items, [], 3)
    assert _titles(picked) == ["News 1", "News 3", "News 2"]
    assert "repito openai" in capsys.readouterr().out


class _FakeLLM:
    def __init__(self, ranking: Ranking):
        self._ranking = ranking

    def with_structured_output(self, _schema):
        return self

    def invoke(self, _messages):
        return self._ranking


def test_ranker_node_enforces_variety_when_model_ignores_it(monkeypatch):
    scored = [_item(1, "openai", 9), _item(2, "openai", 9), _item(3, "openai", 8), _item(4, "anthropic", 7)]
    ranking = Ranking.model_validate(
        {
            "selected": [
                {"index": 1, "final_score": 10, "rationale": "a"},
                {"index": 2, "final_score": 8, "rationale": "b"},
                {"index": 3, "final_score": 7, "rationale": "c"},
            ]
        }
    )
    monkeypatch.setattr(ranker, "get_chat_model", lambda: _FakeLLM(ranking))
    monkeypatch.setattr(ranker, "MAX_ARTICLES", 3)
    out = ranker.ranker_node({"scored_articles": scored})["selected_articles"]
    companies = [it.evaluation.company for it in out]
    assert companies[:2] == ["openai", "anthropic"]
    assert companies.count("openai") == 2  # only 2 companies exist, so one repeat fills the slot
