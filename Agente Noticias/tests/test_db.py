"""Tests for the local SQLite history store (agente_noticias.db)."""
from __future__ import annotations

import sqlite3
import threading
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from agente_noticias import db
from agente_noticias.config import get_db_path


@pytest.fixture()
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "nested" / "history.db"
    monkeypatch.setenv("NEWS_DB_PATH", str(path))
    return path


def _article(n: int, **extra) -> dict:
    return {
        "url": f"https://example.com/news-{n}",
        "normalized_title": f"noticia numero {n}",
        "title": f"Noticia numero {n}",
        "source": "example.com",
        "category": "Industria",
        "relevance_score": 7,
        "published_date": "2026-10-19",
        **extra,
    }


def _save(articles: list[dict], joke: str = "", concepto: str = "") -> str:
    return db.save_briefing(
        subject="Briefing IA",
        recipients="a@win.pe",
        run_id="run-1",
        langsmith_project="agente-noticias-win",
        articles=articles,
        joke=joke,
        joke_normalized=joke.lower(),
        concepto_titulo=concepto,
        concepto_explicacion="explicacion" if concepto else "",
        concepto_normalized=concepto.lower(),
    )


def _age_briefing(path, briefing_id: str, weeks: int) -> None:
    """Moves a briefing (and its articles) `weeks` weeks into the past."""
    old = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).isoformat(timespec="seconds")
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("UPDATE briefings SET sent_at = ? WHERE id = ?", (old, briefing_id))
        conn.execute(
            "UPDATE sent_articles SET sent_at = ? WHERE briefing_id = ?", (old, briefing_id)
        )


def test_db_path_resolves_from_env(db_path):
    assert get_db_path() == db_path


def test_schema_is_created_on_first_use(db_path):
    assert not db_path.exists()

    assert db.fetch_recent_sent(6) == []

    assert db_path.exists()
    with closing(sqlite3.connect(db_path)) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        columns = {r[1] for r in conn.execute("PRAGMA table_info(sent_articles)")}
        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert {"briefings", "sent_articles"} <= tables
    assert {"company", "image_path", "url", "normalized_title", "sent_at"} <= columns
    assert journal == "wal"


def test_save_and_read_back(db_path):
    briefing_id = _save(
        [_article(1, company="OpenAI", image_path="data/images/1.png"), _article(2)],
        joke="Un chiste de IA",
        concepto="Que es un agente",
    )

    assert briefing_id
    sent = db.fetch_recent_sent(6)
    assert sorted(r["url"] for r in sent) == [
        "https://example.com/news-1",
        "https://example.com/news-2",
    ]
    assert {r["normalized_title"] for r in sent} == {"noticia numero 1", "noticia numero 2"}
    assert db.fetch_recent_jokes(6) == ["Un chiste de IA"]
    assert db.fetch_recent_concepts(6) == ["Que es un agente"]

    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute(
            "SELECT company, image_path, week_iso FROM sent_articles WHERE url = ?",
            ("https://example.com/news-1",),
        ).fetchone()
        count = conn.execute(
            "SELECT article_count FROM briefings WHERE id = ?", (briefing_id,)
        ).fetchone()[0]
    assert row[0] == "OpenAI"
    assert row[1] == "data/images/1.png"
    assert row[2].startswith(str(datetime.now(timezone.utc).isocalendar().year))
    assert count == 2


def test_empty_joke_and_concept_are_not_returned(db_path):
    _save([_article(1)])

    assert db.fetch_recent_jokes(6) == []
    assert db.fetch_recent_concepts(6) == []


def test_dedup_window_excludes_old_history(db_path):
    recent_id = _save([_article(1)], joke="chiste reciente", concepto="concepto reciente")
    old_id = _save([_article(2)], joke="chiste viejo", concepto="concepto viejo")
    _age_briefing(db_path, old_id, weeks=8)

    assert recent_id and old_id
    assert [r["url"] for r in db.fetch_recent_sent(6)] == ["https://example.com/news-1"]
    assert db.fetch_recent_jokes(6) == ["chiste reciente"]
    assert db.fetch_recent_concepts(6) == ["concepto reciente"]
    # A wider window includes the old briefing again.
    assert len(db.fetch_recent_sent(10)) == 2


def test_concurrent_writes_do_not_raise(db_path):
    errors: list[BaseException] = []
    ids: list[str] = []

    def worker(n: int) -> None:
        try:
            ids.append(_save([_article(n * 10 + i) for i in range(3)]))
            db.fetch_recent_sent(6)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert all(ids) and len(ids) == 8
    assert len(db.fetch_recent_sent(6)) == 24


def test_failure_degrades_and_warns(tmp_path, monkeypatch, capsys):
    # A directory where the DB file should be makes sqlite fail to open it.
    bad = tmp_path / "is_a_dir.db"
    bad.mkdir()
    monkeypatch.setenv("NEWS_DB_PATH", str(bad))

    assert db.fetch_recent_sent(6) == []
    assert _save([_article(1)]) == ""
    assert "[db] WARNING" in capsys.readouterr().err


def test_non_numeric_relevance_score_is_coerced_not_raised(db_path):
    articles = [
        _article(1, relevance_score="alto"),
        _article(2, relevance_score=None),
        _article(3, relevance_score="7.6"),
        _article(4, relevance_score=9),
    ]

    briefing_id = _save(articles)

    assert briefing_id
    with closing(sqlite3.connect(db_path)) as conn:
        scores = [
            row[0]
            for row in conn.execute(
                "SELECT relevance_score FROM sent_articles ORDER BY url"
            ).fetchall()
        ]
    assert scores == [0, 0, 7, 9]


def test_malformed_article_degrades_instead_of_raising(db_path, capsys):
    assert _save([_article(1), "not-a-dict"]) == ""  # type: ignore[list-item]
    assert "[db] WARNING" in capsys.readouterr().err
    assert db.fetch_recent_sent(6) == []
