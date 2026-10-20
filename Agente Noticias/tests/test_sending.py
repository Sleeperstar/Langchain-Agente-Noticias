"""Tests for send failure handling and webapp swap resilience (no Outlook, no network)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from agente_noticias import service
from agente_noticias.nodes import outlook_sender
from agente_noticias.schemas import (
    Article,
    ArticleEvaluation,
    Briefing,
    EvaluatedArticle,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def no_tracing(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


_TITLES = {
    1: "OpenAI lanza un agente para programar",
    2: "Google presenta Gemini en Android",
    3: "Meta abre su laboratorio de robotica",
}


def _item(n: int) -> EvaluatedArticle:
    return EvaluatedArticle(
        article=Article(title=_TITLES[n], url=f"https://n.example.com/{n}"),
        evaluation=ArticleEvaluation(
            reasoning="r",
            relevance_score=8,
            category="Industria",
            label_es="L",
            title_es=_TITLES[n],
            summary_es="s",
            company="openai",
        ),
    )


def test_outlook_sender_failure_returns_send_ok_false(monkeypatch, capsys):
    def boom(**kwargs):
        raise RuntimeError("No se pudo conectar con Outlook.")

    monkeypatch.setattr(outlook_sender, "_send_via_outlook", boom)
    out = outlook_sender.outlook_sender_node({"subject": "s", "html_body": "<p>x</p>"})

    assert out["send_ok"] is False
    assert out["send_result"].startswith("ERROR:") and "Outlook" in out["send_result"]
    assert "ERROR" in capsys.readouterr().err


def test_outlook_sender_success_returns_send_ok_true(monkeypatch):
    monkeypatch.setattr(outlook_sender, "_send_via_outlook", lambda **kw: "Correo enviado a x.")
    out = outlook_sender.outlook_sender_node({"subject": "s", "html_body": "<p>x</p>"})
    assert out == {"send_result": "Correo enviado a x.", "send_ok": True}


def test_regenerate_article_survives_card_failure(monkeypatch):
    selected, pool = [_item(1), _item(2)], [_item(3)]
    monkeypatch.setattr(
        service,
        "_DRAFT",
        service.Draft(
            selected=list(selected),
            pool=list(pool),
            briefing=Briefing(headline="h", concepto_titulo="c", concepto_explicacion="e", chiste="j"),
        ),
    )
    monkeypatch.setattr(service, "_refresh_briefing_text", lambda: None)

    def boom(item):
        raise RuntimeError("unexpected card failure")

    monkeypatch.setattr(service, "attach_card_image", boom)
    fn = getattr(service.regenerate_article_auto, "__wrapped__", service.regenerate_article_auto)
    out = fn(0)

    assert out["ok"] is True
    draft = service.current_draft()
    assert draft.selected[0].article.url == pool[0].article.url
    assert draft.selected[0].card_image_path is None
    assert [it.article.url for it in draft.pool] == [selected[0].article.url]


def _load_run_script():
    spec = importlib.util.spec_from_file_location("run_script", PROJECT_ROOT / "scripts" / "run.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("send_ok,expected", [(False, 1), (True, 0)])
def test_run_exit_code_reflects_send_result(monkeypatch, send_ok, expected):
    from agente_noticias import graph

    class FakeGraph:
        def invoke(self, state, config):
            return {
                "send_ok": send_ok,
                "send_result": "x",
                "run_id": "r",
                "selected_articles": [_item(1)],
            }

    monkeypatch.setattr(graph, "build_graph", lambda send=True: FakeGraph())
    monkeypatch.setattr(sys, "argv", ["run.py", "--headless"])
    assert _load_run_script().main() == expected


@pytest.mark.parametrize("argv", [["run.py", "--headless"], ["run.py", "--headless", "--dry-run"]])
def test_run_exit_code_1_when_no_articles(monkeypatch, capsys, argv):
    from agente_noticias import graph

    class FakeGraph:
        def invoke(self, state, config):
            return {
                "send_ok": False,
                "send_result": "no se envio: 0 noticias seleccionadas (minimo 1)",
                "run_id": "r",
                "selected_articles": [],
            }

    monkeypatch.setattr(graph, "build_graph", lambda send=True: FakeGraph())
    monkeypatch.setattr(sys, "argv", argv)
    assert _load_run_script().main() == 1
    assert "boletin vacio" in capsys.readouterr().err
