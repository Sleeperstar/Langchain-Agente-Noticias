"""Email writer node: renders the HTML and saves the local preview.

Renders two versions:
- `preview_path` (output/preview.html): images as base64 data URIs so the file
  renders in a browser.
- `html_body` (what gets sent): images as `cid:` references (WIN logo + one per
  card), the robust way to show embedded images in Outlook. `inline_images` lists
  the (path, Content-ID) pairs the sender must attach.
"""
from __future__ import annotations

import os

from langsmith.run_helpers import get_current_run_tree

from agente_noticias.config import DEFAULT_PROJECT, PREVIEW_PATH, get_model
from agente_noticias.email_template import inline_images, render_email
from agente_noticias.state import NewsState


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

    model = get_model()
    project = os.getenv("LANGSMITH_PROJECT", DEFAULT_PROJECT)

    html = render_email(briefing, selected, model, project, run_id, images="cid")
    preview_html = render_email(briefing, selected, model, project, run_id, images="data")

    PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    PREVIEW_PATH.write_text(preview_html, encoding="utf-8")
    print(f"[email_writer] preview guardado en {PREVIEW_PATH}")

    return {
        "html_body": html,
        "inline_images": inline_images(selected),
        "subject": briefing.headline,
        "preview_path": str(PREVIEW_PATH),
        "run_id": run_id,
    }
