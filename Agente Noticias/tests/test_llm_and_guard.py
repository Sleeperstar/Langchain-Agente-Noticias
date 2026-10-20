"""Tests for the OpenRouter chat-model factory and the empty-newsletter guard (no network)."""
from __future__ import annotations

import pytest
from langgraph.graph import END

from agente_noticias import graph as graph_module
from agente_noticias import llm
from agente_noticias.nodes import evaluator
from agente_noticias.schemas import Article, ArticleEvaluation, EvaluatedArticle

FAKE_KEY = "sk-or-test-not-a-real-key"


@pytest.fixture(autouse=True)
def no_tracing(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


def _item(n: int = 1) -> EvaluatedArticle:
    return EvaluatedArticle(
        article=Article(title=f"Noticia {n}", url=f"https://n.example.com/{n}"),
        evaluation=ArticleEvaluation(
            reasoning="r",
            relevance_score=8,
            category="Industria",
            label_es="L",
            title_es=f"Noticia {n}",
            summary_es="s",
            company="openai",
        ),
    )


# --------------------------------------------------------------------------- #
# Chat-model factory
# --------------------------------------------------------------------------- #
def test_get_chat_model_points_to_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("NEWS_MODEL", raising=False)

    model = llm.get_chat_model()

    assert type(model).__name__ == "ChatOpenAI"
    assert model.openai_api_base == "https://openrouter.ai/api/v1"
    assert model.openai_api_key.get_secret_value() == FAKE_KEY
    assert model.model_name == "openai/gpt-5-mini"
    assert model.default_headers["X-Title"] == "Agente Noticias WIN"


def test_get_chat_model_respects_news_model_override(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    monkeypatch.setenv("NEWS_MODEL", "openai/gpt-5")
    assert llm.get_chat_model().model_name == "openai/gpt-5"


def test_get_chat_model_missing_key_fails_fast(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(llm.MissingOpenRouterKeyError, match="OPENROUTER_API_KEY"):
        llm.get_chat_model()


def test_structured_output_uses_strict_json_schema(monkeypatch):
    from openai.lib._parsing._completions import type_to_response_format_param

    monkeypatch.setenv("OPENROUTER_API_KEY", FAKE_KEY)
    bound = llm.get_chat_model().with_structured_output(ArticleEvaluation).first

    assert bound.kwargs["ls_structured_output_format"]["kwargs"]["method"] == "json_schema"
    # The Pydantic class is passed through; the OpenAI SDK turns it into strict json_schema.
    assert bound.kwargs["response_format"] is ArticleEvaluation
    fmt = type_to_response_format_param(ArticleEvaluation)
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True


# --------------------------------------------------------------------------- #
# Evaluator: one summary line when every evaluation fails
# --------------------------------------------------------------------------- #
def test_evaluator_logs_summary_when_all_fail(monkeypatch, capsys):
    class Boom:
        def invoke(self, messages):
            raise RuntimeError("Error code: 429 insufficient_quota")

    monkeypatch.setattr(evaluator, "_build_evaluator", lambda: Boom())
    articles = [Article(title=f"t{i}", url=f"https://n.example.com/{i}") for i in range(3)]

    out = evaluator.evaluator_node({"raw_articles": articles})

    assert out == {"scored_articles": []}
    err = capsys.readouterr().err
    assert "fallaron las 3 evaluaciones" in err and "insufficient_quota" in err


# --------------------------------------------------------------------------- #
# Empty-newsletter guard
# --------------------------------------------------------------------------- #
def test_route_after_email_writer():
    route = graph_module.route_after_email_writer
    assert route({"selected_articles": []}, send=True) == graph_module.NO_ARTICLES_NODE
    assert route({}, send=False) == graph_module.NO_ARTICLES_NODE
    assert route({"selected_articles": [_item()]}, send=True) == "outlook_sender"
    assert route({"selected_articles": [_item()]}, send=False) == END


def _stub_pipeline(monkeypatch, selected):
    """Replaces every node so the compiled graph runs offline; records send/persist calls."""
    calls: list[str] = []
    monkeypatch.setattr(graph_module, "researcher_node", lambda s: {"raw_articles": []})
    monkeypatch.setattr(graph_module, "history_filter_node", lambda s: {"dropped_by_history": 0})
    monkeypatch.setattr(graph_module, "evaluator_node", lambda s: {"scored_articles": []})
    monkeypatch.setattr(graph_module, "ranker_node", lambda s: {"selected_articles": selected})
    monkeypatch.setattr(graph_module, "summarizer_node", lambda s: {"run_id": ""})
    monkeypatch.setattr(graph_module, "card_images_node", lambda s: {"dropped_by_history": 0})
    monkeypatch.setattr(graph_module, "email_writer_node", lambda s: {"subject": "s", "html_body": "<p/>"})

    def fake_send(state):
        calls.append("outlook_sender")
        return {"send_result": "sent", "send_ok": True}

    def fake_persist(state):
        calls.append("persist_history")
        return {"briefing_id": "b1"}

    monkeypatch.setattr(graph_module, "outlook_sender_node", fake_send)
    monkeypatch.setattr(graph_module, "persist_history_node", fake_persist)
    return calls


@pytest.mark.parametrize("send", [True, False])
def test_graph_does_not_send_empty_newsletter(monkeypatch, send):
    calls = _stub_pipeline(monkeypatch, selected=[])

    result = graph_module.build_graph(send=send).invoke({})

    assert calls == []
    assert result["send_ok"] is False
    assert result["send_result"].startswith("no se envio: 0 noticias seleccionadas")


def test_graph_sends_when_articles_selected(monkeypatch):
    calls = _stub_pipeline(monkeypatch, selected=[_item()])

    result = graph_module.build_graph(send=True).invoke({})

    assert calls == ["outlook_sender", "persist_history"]
    assert result["send_ok"] is True
