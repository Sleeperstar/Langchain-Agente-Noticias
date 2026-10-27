"""Tests for the review-before-send flow: dry-run draft + scripts/send_draft.py.

No network, no Outlook: `_send_via_outlook` is monkeypatched and the history DB
lives in a tmp SQLite file (NEWS_DB_PATH).
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest

from agente_noticias import draft as draft_module
from agente_noticias.nodes import outlook_sender
from agente_noticias.schemas import Article, ArticleEvaluation, Briefing, EvaluatedArticle

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def isolated(monkeypatch, tmp_path):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("NEWS_DB_PATH", str(tmp_path / "history.db"))
    monkeypatch.setattr(draft_module, "DRAFT_DIR", tmp_path / "draft")


def _load_script(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_script", PROJECT_ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _item(n: int, image: Path | None = None) -> EvaluatedArticle:
    item = EvaluatedArticle(
        article=Article(title=f"Original title {n}", url=f"https://n.example.com/{n}", source="example.com"),
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
    item.card_image_path = str(image) if image else None
    return item


def _state(tmp_path: Path, n_articles: int = 2) -> dict:
    src = tmp_path / "src"
    src.mkdir(exist_ok=True)
    header = src / "header.png"
    header.write_bytes(b"header-bytes")
    selected, images = [], [(str(header), "header")]
    for i in range(n_articles):
        card = src / f"card{i + 1}.png"
        card.write_bytes(b"card-bytes-%d" % i)
        selected.append(_item(i + 1, card))
        images.append((str(card), f"card{i + 1}"))
    html = "<p>" + "".join(f'<img src="cid:{cid}">' for _, cid in images) + "</p>"
    return {
        "subject": "Noticias IA de la semana",
        "html_body": html,
        "inline_images": images,
        "selected_articles": selected,
        "briefing": Briefing(headline="h", concepto_titulo="RAG", concepto_explicacion="e", chiste="j"),
        "run_id": "run-123",
        "preview_path": str(tmp_path / "preview.html"),
        "send_ok": False,
        "send_result": "",
    }


def _history_rows(db_path: Path) -> tuple[list, list]:
    if not db_path.exists():
        return [], []
    with closing(sqlite3.connect(db_path)) as conn:
        briefings = conn.execute("SELECT subject, recipients, run_id, article_count, joke FROM briefings").fetchall()
        articles = conn.execute("SELECT url, title FROM sent_articles ORDER BY id").fetchall()
    return briefings, articles


# --------------------------------------------------------------------------- #
# Draft persistence (run.py --dry-run)
# --------------------------------------------------------------------------- #
def _run_dry(monkeypatch, state: dict) -> int:
    from agente_noticias import graph

    class FakeGraph:
        def invoke(self, s, config):
            return state

    monkeypatch.setattr(graph, "build_graph", lambda send=True: FakeGraph())
    monkeypatch.setattr(sys, "argv", ["run.py", "--headless", "--dry-run"])
    return _load_script("run").main()


def test_dry_run_writes_draft_with_copied_images(monkeypatch, tmp_path, capsys):
    state = _state(tmp_path)
    assert _run_dry(monkeypatch, state) == 0

    draft_path = tmp_path / "draft" / "draft.json"
    data = json.loads(draft_path.read_text(encoding="utf-8"))
    assert data["schema_version"] == draft_module.SCHEMA_VERSION
    assert data["subject"] == state["subject"]
    assert data["html"] == state["html_body"]
    assert data["run_id"] == "run-123"
    assert data["sent_at"] is None and data["sent_to"] is None
    assert data["news_titles"] == ["Noticia 1", "Noticia 2"]
    assert [img["cid"] for img in data["inline_images"]] == ["header", "card1", "card2"]
    for img, (src, _) in zip(data["inline_images"], state["inline_images"]):
        copied = draft_path.parent / img["file"]
        assert copied.is_file() and copied.read_bytes() == Path(src).read_bytes()
        assert copied.parent == draft_path.parent / "images"
    history = data["history"]
    assert [a["url"] for a in history["articles"]] == ["https://n.example.com/1", "https://n.example.com/2"]
    assert history["joke"] == "j" and history["concepto_titulo"] == "RAG"
    assert str(draft_path) in capsys.readouterr().out


def test_dry_run_without_articles_writes_no_draft(monkeypatch, tmp_path):
    state = _state(tmp_path, n_articles=0)
    assert _run_dry(monkeypatch, state) == 1
    assert not (tmp_path / "draft").exists()


def test_save_draft_replaces_unsent_previous_draft(tmp_path, capsys):
    draft_module.save_draft(_state(tmp_path), model="m")
    capsys.readouterr()
    draft_module.save_draft(_state(tmp_path, n_articles=1), model="m")
    out = capsys.readouterr().out
    assert "se reemplaza el borrador anterior" in out and "NO se habia enviado" in out
    images = sorted(p.name for p in (tmp_path / "draft" / "images").iterdir())
    assert images == ["card1.png", "header.png"]


# --------------------------------------------------------------------------- #
# scripts/send_draft.py
# --------------------------------------------------------------------------- #
@pytest.fixture()
def saved_draft(tmp_path) -> Path:
    return draft_module.save_draft(_state(tmp_path), model="test-model")


@pytest.fixture()
def sent_calls(monkeypatch) -> list[dict]:
    calls: list[dict] = []

    def fake_send(**kwargs):
        calls.append(kwargs)
        return f"Correo enviado a {kwargs['to']} via Outlook Desktop."

    monkeypatch.setattr(outlook_sender, "_send_via_outlook", fake_send)
    return calls


def _send(argv: list[str], answer: str = "") -> int:
    return _load_script("send_draft").main(argv, input_fn=lambda prompt: answer)


def test_send_with_yes_sends_exact_draft_persists_and_marks(saved_draft, sent_calls, tmp_path):
    before = json.loads(saved_draft.read_text(encoding="utf-8"))

    code = _send(["--to", "a@win.pe, b@win.pe,A@win.pe", "--draft", str(saved_draft), "--yes"])

    assert code == 0
    assert len(sent_calls) == 1
    call = sent_calls[0]
    assert call["to"] == "a@win.pe; b@win.pe"
    assert call["subject"] == before["subject"]
    assert call["html_body"] == before["html"]
    assert call["inline_images"] == [
        (str(saved_draft.parent / img["file"]), img["cid"]) for img in before["inline_images"]
    ]
    briefings, articles = _history_rows(tmp_path / "history.db")
    assert briefings == [("Noticias IA de la semana", "a@win.pe, b@win.pe", "run-123", 2, "j")]
    assert [a[0] for a in articles] == ["https://n.example.com/1", "https://n.example.com/2"]
    after = json.loads(saved_draft.read_text(encoding="utf-8"))
    assert after["sent_at"] and after["sent_to"] == ["a@win.pe", "b@win.pe"]


def test_send_refuses_already_sent_draft_unless_forced(saved_draft, sent_calls):
    draft_module.mark_sent(saved_draft, ["x@win.pe"])

    assert _send(["--to", "a@win.pe", "--draft", str(saved_draft), "--yes"]) == 1
    assert sent_calls == []

    assert _send(["--to", "a@win.pe", "--draft", str(saved_draft), "--yes", "--force"]) == 0
    assert len(sent_calls) == 1


def test_send_refuses_missing_image(saved_draft, sent_calls, capsys):
    (saved_draft.parent / "images" / "card1.png").unlink()

    assert _send(["--to", "a@win.pe", "--draft", str(saved_draft), "--yes"]) == 1
    assert sent_calls == []
    assert "faltan imagenes" in capsys.readouterr().err


def test_send_refuses_draft_without_articles(tmp_path, sent_calls):
    path = draft_module.save_draft(_state(tmp_path, n_articles=0), model="m")
    assert _send(["--to", "a@win.pe", "--draft", str(path), "--yes"]) == 1
    assert sent_calls == []


@pytest.mark.parametrize("to", ["not-an-email", "a@win.pe,b@", "a@win.pe;b@win.pe", " , "])
def test_send_rejects_invalid_recipients(saved_draft, sent_calls, to):
    assert _send(["--to", to, "--draft", str(saved_draft), "--yes"]) == 1
    assert sent_calls == []


def test_send_failure_exits_1_without_marking_or_history(saved_draft, monkeypatch, tmp_path):
    def boom(**kwargs):
        raise RuntimeError("No se pudo conectar con Outlook.")

    monkeypatch.setattr(outlook_sender, "_send_via_outlook", boom)
    before = saved_draft.read_text(encoding="utf-8")

    assert _send(["--to", "a@win.pe", "--draft", str(saved_draft), "--yes"]) == 1
    assert saved_draft.read_text(encoding="utf-8") == before
    assert _history_rows(tmp_path / "history.db")[0] == []


@pytest.mark.parametrize("answer,expected,n_calls", [("n", 2, 0), ("", 2, 0), ("s", 0, 1), ("SI", 0, 1)])
def test_send_confirmation_prompt(saved_draft, sent_calls, answer, expected, n_calls):
    assert _send(["--to", "a@win.pe", "--draft", str(saved_draft)], answer=answer) == expected
    assert len(sent_calls) == n_calls
    sent = json.loads(saved_draft.read_text(encoding="utf-8"))["sent_at"]
    assert bool(sent) is bool(n_calls)


def test_send_missing_draft_exits_1(tmp_path, sent_calls):
    assert _send(["--to", "a@win.pe", "--draft", str(tmp_path / "nope.json"), "--yes"]) == 1
    assert sent_calls == []
