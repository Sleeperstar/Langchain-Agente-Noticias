"""Local SQLite store for the news anti-repetition history.

Tables `briefings` and `sent_articles` live in one SQLite file at NEWS_DB_PATH
(default: `<project>/data/agente_noticias.db`). The schema is created
idempotently on first use. Card images are stored as files on disk; the DB only
keeps their relative path (`sent_articles.image_path`).

If a DB operation fails, functions log a warning to stderr and degrade safely
(no filtering / no persistence) so the agent keeps working.
"""
from __future__ import annotations

import sqlite3
import sys
import threading
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timedelta, timezone
from typing import Iterator

from agente_noticias.config import get_db_path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS briefings (
    id                   TEXT PRIMARY KEY,
    sent_at              TEXT NOT NULL,
    subject              TEXT,
    recipients           TEXT,
    run_id               TEXT,
    article_count        INTEGER,
    langsmith_project    TEXT,
    joke                 TEXT,
    joke_normalized      TEXT,
    concepto_titulo      TEXT,
    concepto_explicacion TEXT,
    concepto_normalized  TEXT
);

CREATE TABLE IF NOT EXISTS sent_articles (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    briefing_id      TEXT NOT NULL REFERENCES briefings(id) ON DELETE CASCADE,
    sent_at          TEXT NOT NULL,
    url              TEXT,
    normalized_title TEXT,
    title            TEXT,
    source           TEXT,
    category         TEXT,
    relevance_score  INTEGER,
    published_date   TEXT,
    week_iso         TEXT,
    company          TEXT,
    image_path       TEXT
);

CREATE INDEX IF NOT EXISTS idx_briefings_sent_at ON briefings(sent_at);
CREATE INDEX IF NOT EXISTS idx_sent_articles_url ON sent_articles(url);
CREATE INDEX IF NOT EXISTS idx_sent_articles_normalized_title ON sent_articles(normalized_title);
CREATE INDEX IF NOT EXISTS idx_sent_articles_sent_at ON sent_articles(sent_at);
"""

# Nodes run in threads: serialize schema creation and writes inside the process.
# Reads go through WAL and do not need the lock.
_SCHEMA_LOCK = threading.Lock()
_WRITE_LOCK = threading.Lock()
_READY_PATHS: set[str] = set()


def _warn(message: str) -> None:
    print(f"[db] WARNING: {message}", file=sys.stderr)


def _now_iso() -> str:
    # Fixed format so ISO strings compare correctly as text.
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _since_iso(weeks: int) -> str:
    since = datetime.now(timezone.utc) - timedelta(weeks=weeks)
    return since.isoformat(timespec="seconds")


def _as_int(value: object, default: int = 0) -> int:
    """Tolerant int coercion for scores coming from LLM output (never raises)."""
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        pass
    try:
        return int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError, OverflowError):
        return default


def _ensure_schema(conn: sqlite3.Connection, key: str) -> None:
    if key in _READY_PATHS:
        return
    with _SCHEMA_LOCK:
        if key in _READY_PATHS:
            return
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA_SQL)
        _READY_PATHS.add(key)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Opens a short-lived connection (one per call) with the schema in place."""
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(str(path), timeout=30)) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        _ensure_schema(conn, str(path.resolve()))
        yield conn


def fetch_recent_sent(weeks: int) -> list[dict]:
    """Returns [{url, normalized_title}] of articles sent in the last `weeks` weeks."""
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT url, normalized_title FROM sent_articles WHERE sent_at >= ?",
                (_since_iso(weeks),),
            ).fetchall()
        return [dict(row) for row in rows]
    except Exception as exc:  # noqa: BLE001
        _warn(f"failed to read article history (no filtering): {exc}")
        return []


def fetch_recent_jokes(weeks: int) -> list[str]:
    """Returns the jokes sent in the last `weeks` weeks (text)."""
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT joke FROM briefings WHERE sent_at >= ? AND joke <> ''",
                (_since_iso(weeks),),
            ).fetchall()
        return [row["joke"] for row in rows]
    except Exception as exc:  # noqa: BLE001
        _warn(f"failed to read recent jokes: {exc}")
        return []


def fetch_recent_concepts(weeks: int) -> list[str]:
    """Returns the 'concepto del dia' titles used in the last `weeks` weeks."""
    try:
        with connect() as conn:
            rows = conn.execute(
                "SELECT concepto_titulo FROM briefings"
                " WHERE sent_at >= ? AND concepto_titulo <> ''",
                (_since_iso(weeks),),
            ).fetchall()
        return [row["concepto_titulo"] for row in rows]
    except Exception as exc:  # noqa: BLE001
        _warn(f"failed to read recent concepts: {exc}")
        return []


def save_briefing(
    subject: str,
    recipients: str,
    run_id: str,
    langsmith_project: str,
    articles: list[dict],
    joke: str = "",
    joke_normalized: str = "",
    concepto_titulo: str = "",
    concepto_explicacion: str = "",
    concepto_normalized: str = "",
) -> str:
    """Inserts a briefing and its articles atomically. Returns the briefing_id or '' on failure.

    `articles` is a list of dicts with: url, normalized_title, title, source,
    category, relevance_score, published_date and, optionally, company and
    image_path (path of the card PNG relative to the project).
    """
    now = datetime.now(timezone.utc)
    sent_at = _now_iso()
    week_iso = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"
    briefing_id = str(uuid.uuid4())

    try:
        # Built inside the try: malformed article dicts degrade like a DB error.
        article_rows = [
            (
                briefing_id,
                sent_at,
                a.get("url", ""),
                a.get("normalized_title", ""),
                a.get("title", ""),
                a.get("source", ""),
                a.get("category", ""),
                _as_int(a.get("relevance_score")),
                a.get("published_date", ""),
                week_iso,
                a.get("company") or None,
                a.get("image_path") or None,
            )
            for a in articles
        ]
        # `with conn` wraps both inserts in one transaction (commit or rollback).
        with _WRITE_LOCK, connect() as conn, conn:
            conn.execute(
                "INSERT INTO briefings (id, sent_at, subject, recipients, run_id,"
                " article_count, langsmith_project, joke, joke_normalized,"
                " concepto_titulo, concepto_explicacion, concepto_normalized)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    briefing_id,
                    sent_at,
                    subject,
                    recipients,
                    run_id,
                    len(articles),
                    langsmith_project,
                    joke,
                    joke_normalized,
                    concepto_titulo,
                    concepto_explicacion,
                    concepto_normalized,
                ),
            )
            conn.executemany(
                "INSERT INTO sent_articles (briefing_id, sent_at, url, normalized_title,"
                " title, source, category, relevance_score, published_date, week_iso,"
                " company, image_path)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                article_rows,
            )
        return briefing_id
    except Exception as exc:  # noqa: BLE001
        _warn(f"failed to save history (nothing persisted): {exc}")
        return ""
