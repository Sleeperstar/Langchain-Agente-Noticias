"""Email writer node: renderiza HTML y guarda preview local.

Genera dos versiones del HTML:
- `preview_path` (output/preview.html): usa el logo como data URI base64 para que
  se vea en el navegador.
- `html_body` (lo que se envia): usa `cid:winlogo`, que es el metodo robusto para
  mostrar imagenes embebidas en Outlook (el sender adjunta el PNG con ese CID).
"""
from __future__ import annotations

import os

from langsmith.run_helpers import get_current_run_tree

from agente_noticias.config import DEFAULT_PROJECT, LOGO_PATH, PREVIEW_PATH, get_model
from agente_noticias.email_template import logo_data_uri, render_email
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

    # Version para enviar: logo embebido por CID (si existe el archivo).
    email_logo_src = "cid:winlogo" if LOGO_PATH.exists() else ""
    html = render_email(
        briefing=briefing,
        selected=selected,
        model=model,
        project=project,
        run_id=run_id,
        logo_src=email_logo_src,
    )

    # Version para previsualizar en navegador: logo como data URI.
    preview_html = render_email(
        briefing=briefing,
        selected=selected,
        model=model,
        project=project,
        run_id=run_id,
        logo_src=logo_data_uri(),
    )

    subject = briefing.headline

    PREVIEW_PATH.write_text(preview_html, encoding="utf-8")
    print(f"[email_writer] preview guardado en {PREVIEW_PATH}")

    return {
        "html_body": html,
        "subject": subject,
        "preview_path": str(PREVIEW_PATH),
        "run_id": run_id,
    }
