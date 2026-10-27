"""Send-ready newsletter draft (review first, send later).

`run.py --dry-run` saves the exact email that would be sent into `output/draft/`:

    output/draft/draft.json      subject, CID-mode HTML, inline image list, history payload
    output/draft/images/<cid>.*  copies of the inline images (later runs cannot overwrite them)

`scripts/send_draft.py` loads it, sends that same HTML via Outlook, persists the
history and marks the draft as sent (`sent_at`, `sent_to`).
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from agente_noticias.config import DEFAULT_PROJECT, OUTPUT_DIR, get_model
from agente_noticias.nodes.persist_history import history_payload

SCHEMA_VERSION = 1
DRAFT_DIR = OUTPUT_DIR / "draft"
DRAFT_FILENAME = "draft.json"
IMAGES_SUBDIR = "images"


class DraftError(RuntimeError):
    """The draft file is missing, unreadable or has an unsupported schema."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_json(path: Path, data: dict) -> None:
    # Write to a sibling temp file, then replace: a crash never leaves half a draft.
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _news_titles(selected: list) -> list[str]:
    return [item.evaluation.title_es or item.article.title for item in selected]


def save_draft(state: dict, draft_dir: Path | None = None, model: str | None = None) -> Path:
    """Saves the send-ready draft from a final graph state; returns the draft.json path.

    Replaces any previous draft (and its copied images). The caller must only call
    this when the empty-newsletter guard passed.
    """
    draft_dir = Path(draft_dir or DRAFT_DIR)
    draft_path = draft_dir / DRAFT_FILENAME
    images_dir = draft_dir / IMAGES_SUBDIR

    if draft_path.is_file():
        try:
            previous = json.loads(draft_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = {}
        print(f"[draft] se reemplaza el borrador anterior ({previous.get('created_at', '?')})")
        if not previous.get("sent_at"):
            print("[draft] AVISO: el borrador anterior NO se habia enviado.")

    draft_dir.mkdir(parents=True, exist_ok=True)
    if images_dir.exists():
        shutil.rmtree(images_dir)
    images_dir.mkdir(parents=True)

    images = []
    for src, cid in state.get("inline_images") or []:
        src_path = Path(src)
        dest = images_dir / f"{cid}{src_path.suffix or '.png'}"
        shutil.copy2(src_path, dest)
        images.append({"cid": cid, "file": dest.relative_to(draft_dir).as_posix()})

    selected = state.get("selected_articles") or []
    data = {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now_iso(),
        "run_id": state.get("run_id", ""),
        "model": model or get_model(),
        "langsmith_project": os.getenv("LANGSMITH_PROJECT", DEFAULT_PROJECT),
        "subject": state.get("subject", ""),
        "html": state.get("html_body", ""),
        "inline_images": images,
        "news_titles": _news_titles(selected),
        "history": history_payload(selected, state.get("briefing")),
        "sent_at": None,
        "sent_to": None,
    }
    _write_json(draft_path, data)
    print(f"[draft] borrador listo para enviar en {draft_path}")
    return draft_path


def load_draft(path: Path | str) -> dict:
    """Reads a draft.json; raises DraftError if missing, unreadable or of another schema."""
    path = Path(path)
    if not path.is_file():
        raise DraftError(f"no existe el borrador {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise DraftError(f"no se pudo leer el borrador {path}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        raise DraftError(f"version de borrador no soportada en {path}")
    return data


def image_paths(draft: dict, draft_path: Path | str) -> list[tuple[str, str]]:
    """(absolute file path, cid) pairs, as `_send_via_outlook` expects them."""
    base = Path(draft_path).parent
    return [(str(base / img["file"]), img["cid"]) for img in draft.get("inline_images", [])]


def mark_sent(draft_path: Path | str, recipients: list[str]) -> dict:
    """Stamps `sent_at`/`sent_to` on the draft file; returns the updated draft."""
    draft_path = Path(draft_path)
    data = load_draft(draft_path)
    data["sent_at"] = _now_iso()
    data["sent_to"] = list(recipients)
    _write_json(draft_path, data)
    return data
