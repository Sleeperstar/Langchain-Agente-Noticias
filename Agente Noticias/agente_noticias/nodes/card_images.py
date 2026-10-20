"""Card images node: builds the newsletter card PNG of each selected article in parallel.

Runs in parallel with `summarizer` (both after `ranker`) and before `email_writer`.
Image problems never fail the run: `card_images.build_card_image` falls back to
og:image / a branded placeholder, and an unexpected error leaves the card unset.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from agente_noticias._concurrency import submit_with_context
from agente_noticias.card_images import build_card_image, card_filename
from agente_noticias.config import CARD_IMAGES_DIR, PROJECT_DIR
from agente_noticias.schemas import EvaluatedArticle
from agente_noticias.state import NewsState


def project_relative(path: str | None) -> str | None:
    """Path relative to the project root (POSIX style) for the history DB."""
    if not path:
        return None
    p = Path(path)
    try:
        return p.resolve().relative_to(PROJECT_DIR.resolve()).as_posix()
    except ValueError:
        return str(p)


def attach_card_image(item: EvaluatedArticle, out_dir: Path | None = None) -> EvaluatedArticle:
    """Returns a copy of `item` with `card_image_path` set (unchanged copy on failure)."""
    a, e = item.article, item.evaluation
    out_dir = out_dir or CARD_IMAGES_DIR / date.today().isoformat()
    try:
        path = build_card_image(
            out_path=out_dir / card_filename(a.title, a.url),
            title=a.title,
            summary=e.summary_es,
            visual_subject=e.visual_subject,
            company=e.company,
            image_url=a.image_url,
            article_url=a.url,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[card_images] WARNING: no card for {a.url}: {exc}", file=sys.stderr)
        return item.model_copy()
    return item.model_copy(update={"card_image_path": str(path)})


def card_images_node(state: NewsState) -> dict:
    selected = state.get("selected_articles", []) or []
    if not selected:
        return {}

    out_dir = CARD_IMAGES_DIR / date.today().isoformat()
    results: list[EvaluatedArticle] = list(selected)
    with ThreadPoolExecutor(max_workers=min(5, len(selected))) as pool:
        futures = {
            submit_with_context(pool, attach_card_image, item, out_dir): i
            for i, item in enumerate(selected)
        }
        for fut in as_completed(futures):
            results[futures[fut]] = fut.result()

    done = sum(1 for it in results if it.card_image_path)
    print(f"[card_images] {done}/{len(results)} tarjetas generadas en {out_dir}")
    return {"selected_articles": results}
