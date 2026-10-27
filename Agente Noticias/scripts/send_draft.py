"""Envia por Outlook EXACTAMENTE el borrador generado con `run.py --dry-run`.

Flujo "revisar antes de enviar":

    uv run python scripts/run.py --dry-run                       # 1. preview + borrador
    # 2. revisa output/preview.html
    uv run python scripts/send_draft.py --to persona1@win.pe,persona2@win.pe   # 3. envia

Opciones:
    --draft RUTA   borrador a enviar (default: output/draft/draft.json)
    --yes          no pide confirmacion interactiva
    --force        permite reenviar un borrador ya enviado

Codigos de salida: 0 enviado, 1 error/rechazo, 2 cancelado por el usuario.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

EXIT_SENT, EXIT_FAILED, EXIT_ABORTED = 0, 1, 2
_EMAIL_RE = re.compile(r"^[^@\s;,<>]+@[^@\s;,<>]+\.[^@\s;,<>]+$")
_YES = {"s", "si", "sí", "y", "yes"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Envia por Outlook el borrador revisado (generado con run.py --dry-run)."
    )
    parser.add_argument("--to", required=True,
                        help="Destinatarios separados por comas (ej. a@win.pe,b@win.pe).")
    parser.add_argument("--draft", default=None,
                        help="Ruta del draft.json (default: output/draft/draft.json).")
    parser.add_argument("--yes", action="store_true",
                        help="No pide confirmacion antes de enviar.")
    parser.add_argument("--force", action="store_true",
                        help="Permite reenviar un borrador que ya fue enviado.")
    return parser.parse_args(argv)


def parse_recipients(raw: str) -> tuple[list[str], list[str]]:
    """Splits a comma-separated list; returns (valid deduped recipients, invalid entries)."""
    valid: list[str] = []
    invalid: list[str] = []
    seen: set[str] = set()
    for part in raw.split(","):
        email = part.strip()
        if not email:
            continue
        if not _EMAIL_RE.match(email):
            invalid.append(email)
            continue
        if email.lower() not in seen:
            seen.add(email.lower())
            valid.append(email)
    return valid, invalid


def _error(message: str) -> int:
    print(f"[send_draft] ERROR: {message}", file=sys.stderr)
    return EXIT_FAILED


def _print_summary(draft: dict, recipients: list[str], images: list[tuple[str, str]]) -> None:
    from agente_noticias.card_images import MAX_CARD_BYTES

    titles = draft.get("news_titles") or []
    print("=== Borrador a enviar ===")
    print(f"Asunto:        {draft.get('subject')}")
    print(f"Creado:        {draft.get('created_at')}  (modelo {draft.get('model')})")
    print(f"Noticias ({len(titles)}):")
    for title in titles:
        print(f"  - {title}")
    print(f"Destinatarios ({len(recipients)}): {', '.join(recipients)}")
    print(f"Imagenes inline: {len(images)}")
    for path, cid in images:
        p = Path(path)
        if not p.is_file():
            print(f"  - {cid}: FALTA {p}")
            continue
        size = p.stat().st_size
        warn = "  AVISO: > 100 KB, Outlook web podria mostrarla en blanco" if size > MAX_CARD_BYTES else ""
        print(f"  - {cid}: {size / 1024:.1f} KB{warn}")
    if draft.get("sent_at"):
        print(f"YA ENVIADO:    {draft['sent_at']} a {', '.join(draft.get('sent_to') or [])}")


def main(argv: list[str] | None = None, input_fn: Callable[[str], str] = input) -> int:
    args = parse_args(argv)

    import agente_noticias  # noqa: F401  (dispara load_environment)
    from agente_noticias import draft as draft_module
    from agente_noticias.db import save_briefing
    from agente_noticias.nodes import outlook_sender

    recipients, invalid = parse_recipients(args.to)
    if invalid:
        return _error(f"direcciones invalidas: {', '.join(invalid)}")
    if not recipients:
        return _error("--to no tiene ningun destinatario.")

    draft_path = Path(args.draft) if args.draft else draft_module.DRAFT_DIR / draft_module.DRAFT_FILENAME
    try:
        draft = draft_module.load_draft(draft_path)
    except draft_module.DraftError as exc:
        return _error(f"{exc}. Genera uno con: uv run python scripts/run.py --dry-run")

    images = draft_module.image_paths(draft, draft_path)
    _print_summary(draft, recipients, images)

    history = draft.get("history") or {}
    if not history.get("articles"):
        return _error("el borrador no tiene noticias; no se envia un boletin vacio.")
    if draft.get("sent_at") and not args.force:
        return _error("este borrador ya fue enviado. Usa --force para reenviarlo.")
    missing = [path for path, _ in images if not Path(path).is_file()]
    if missing:
        return _error(f"faltan imagenes del borrador: {', '.join(missing)}")

    if not args.yes:
        try:
            answer = input_fn("Enviar? [s/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in _YES:
            print("[send_draft] cancelado: no se envio nada.")
            return EXIT_ABORTED

    to = "; ".join(recipients)
    try:
        result = outlook_sender._send_via_outlook(
            to=to,
            subject=draft.get("subject", ""),
            html_body=draft.get("html", ""),
            inline_images=images,
        )
    except Exception as exc:  # noqa: BLE001 - Outlook closed, COM error, etc.
        return _error(f"no se pudo enviar el correo via Outlook: {exc} (borrador sin cambios)")
    print(f"[send_draft] {result}")

    # The email is out: mark the draft as sent FIRST, so a crash while writing the
    # history (or anything after) can never allow an accidental resend.
    draft_module.mark_sent(draft_path, recipients)
    print(f"[send_draft] borrador marcado como enviado: {draft_path}")

    briefing_id = save_briefing(
        subject=draft.get("subject", ""),
        recipients=", ".join(recipients),
        run_id=draft.get("run_id", ""),
        langsmith_project=draft.get("langsmith_project") or os.getenv("LANGSMITH_PROJECT", ""),
        **history,
    )
    if briefing_id:
        print(f"[send_draft] historial guardado (briefing_id={briefing_id})")
    else:
        print("[send_draft] AVISO: el correo se envio pero NO se guardo el historial (ver [db]).",
              file=sys.stderr)
    return EXIT_SENT


if __name__ == "__main__":
    raise SystemExit(main())
