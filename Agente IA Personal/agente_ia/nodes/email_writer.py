"""Email writer node: renderiza HTML y guarda preview local."""
from __future__ import annotations

import os

from langsmith.run_helpers import get_current_run_tree

from agente_ia.config import DEFAULT_PROJECT, PREVIEW_PATH, get_model
from agente_ia.email_template import render_email
from agente_ia.state import NewsState


def email_writer_node(state: NewsState) -> dict:
    briefing = state["briefing"]
    selected = state.get("selected_articles", []) or []

    run_id = ""
    try:
        run = get_current_run_tree()
        if run is not None:
            run_id = str(run.id)
    except Exception:  # noqa: BLE001
        pass

    html = render_email(
        briefing=briefing,
        selected=selected,
        model=get_model(),
        project=os.getenv("LANGSMITH_PROJECT", DEFAULT_PROJECT),
        run_id=run_id,
    )
    subject = briefing.headline

    PREVIEW_PATH.write_text(html, encoding="utf-8")
    print(f"[email_writer] preview guardado en {PREVIEW_PATH}")

    return {
        "html_body": html,
        "subject": subject,
        "preview_path": str(PREVIEW_PATH),
        "run_id": run_id,
    }
