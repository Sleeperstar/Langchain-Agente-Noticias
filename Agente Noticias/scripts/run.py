"""Ejecuta el agente Noticias Win Internet end-to-end.

Uso basico:

    python scripts/run.py                    # on-demand con aprobacion humana
    python scripts/run.py --auto-approve     # envia sin pedir confirmacion
    python scripts/run.py --dry-run          # solo genera preview, no envia
    python scripts/run.py --thread mi-id     # custom thread_id (LangGraph)
    python scripts/run.py --headless         # no abre el navegador con el preview
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
import webbrowser
from datetime import date
from pathlib import Path

# Permitir ejecutar el script tanto desde la raiz del proyecto como desde scripts/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import agente_noticias  # noqa: E402  (dispara load_environment)
from agente_noticias.config import PREVIEW_PATH, get_recipient  # noqa: E402
from agente_noticias.graph import build_graph, default_config  # noqa: E402
from langgraph.types import Command  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agente Noticias Win Internet")
    parser.add_argument("--auto-approve", action="store_true",
                        help="Envia el correo sin pedir confirmacion humana.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Genera el preview HTML pero NO envia el correo.")
    parser.add_argument("--headless", action="store_true",
                        help="No abre el preview en el navegador.")
    parser.add_argument("--thread", type=str, default=None,
                        help="thread_id de LangGraph (por defecto se genera uno con uuid).")
    return parser.parse_args()


def _open_preview() -> None:
    try:
        webbrowser.open(PREVIEW_PATH.as_uri())
    except Exception:  # noqa: BLE001
        pass


def _ask_approval() -> bool:
    answer = input(f"\n>>> Enviar correo a {get_recipient()}? [s/N]: ").strip().lower()
    return answer in {"s", "si", "sí", "y", "yes"}


def main() -> int:
    args = parse_args()

    thread_id = args.thread or f"agente-noticias-{date.today().isoformat()}-{uuid.uuid4().hex[:6]}"
    config = default_config(thread_id=thread_id)
    print(f"[run] thread_id={thread_id}  project={os.getenv('LANGSMITH_PROJECT')}")
    print(f"[run] destinatario={get_recipient()}")

    graph = build_graph()

    # 1. Primera invocacion: corre hasta el interrupt del approval_gate.
    result = graph.invoke({}, config)

    interrupts = result.get("__interrupt__")
    if not interrupts:
        # Algo paso, o ya termino sin pedir aprobacion (no deberia).
        print("[run] flujo termino sin interrupt. Resultado:")
        print(result.get("send_result", "(sin send_result)"))
        return 0

    payload = interrupts[0].value
    print("\n=== Preview generado ===")
    print(f"Asunto:           {payload.get('subject')}")
    print(f"Archivo preview:  {payload.get('preview_path')}")
    print(f"Articulos:        {payload.get('article_count')}")
    print("TL;DR:")
    for b in payload.get("tldr", []):
        print(f"  - {b}")

    if not args.headless:
        _open_preview()

    if args.dry_run:
        print("\n[run] --dry-run activado, no se envia el correo.")
        return 0

    if args.auto_approve:
        approved = True
        print("\n[run] --auto-approve activado, se envia sin confirmar.")
    else:
        approved = _ask_approval()

    # 2. Reanudar el grafo con la decision.
    final = graph.invoke(Command(resume=approved), config)
    print("\n[run] resultado final:")
    print(f"  approved:    {final.get('approved')}")
    print(f"  send_result: {final.get('send_result')}")
    print(f"  run_id:      {final.get('run_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
