"""Ejecuta el Agente IA Personal end-to-end.

Uso basico:

    uv run python scripts/run.py                  # busca, arma briefing y envia por Outlook
    uv run python scripts/run.py --dry-run        # solo genera el preview, NO envia
    uv run python scripts/run.py --headless       # no abre el navegador con el preview
    uv run python scripts/run.py --model gpt-5-mini   # override del modelo
    uv run python scripts/run.py --thread mi-id   # custom thread_id (LangGraph)
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid
import webbrowser
from datetime import date
from pathlib import Path

# Permitir ejecutar el script desde la raiz del proyecto o desde scripts/.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Agente IA Personal")
    parser.add_argument("--dry-run", action="store_true",
                        help="Genera el preview HTML pero NO envia el correo.")
    parser.add_argument("--headless", action="store_true",
                        help="No abre el preview en el navegador.")
    parser.add_argument("--model", type=str, default=None,
                        help="Override del modelo LLM (setea NEWS_MODEL).")
    parser.add_argument("--thread", type=str, default=None,
                        help="thread_id de LangGraph (por defecto se genera con uuid).")
    return parser.parse_args()


def _open_preview(preview_path: str) -> None:
    try:
        webbrowser.open(Path(preview_path).as_uri())
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    args = parse_args()

    # El override de modelo debe ocurrir ANTES de importar el paquete/grafo.
    if args.model:
        os.environ["NEWS_MODEL"] = args.model

    import agente_ia  # noqa: F401  (dispara load_environment)
    from agente_ia.config import get_model, get_recipient
    from agente_ia.graph import build_graph, default_config

    thread_id = args.thread or f"agente-ia-personal-{date.today().isoformat()}-{uuid.uuid4().hex[:6]}"
    config = default_config(thread_id=thread_id)
    print(f"[run] thread_id={thread_id}  project={os.getenv('LANGSMITH_PROJECT')}")
    print(f"[run] modelo={get_model()}  destinatario={get_recipient()}")

    graph = build_graph(send=not args.dry_run)
    result = graph.invoke({}, config)

    briefing = result.get("briefing")
    print("\n=== Briefing generado ===")
    if briefing is not None:
        print(f"Asunto:           {result.get('subject')}")
        print(f"Archivo preview:  {result.get('preview_path')}")
        print(f"Articulos:        {len(result.get('selected_articles', []) or [])}")
        print("TL;DR:")
        for b in briefing.tldr:
            print(f"  - {b}")
        print(f"Skill del dia:    {briefing.skill_of_the_day}")

    if not args.headless and result.get("preview_path"):
        _open_preview(result["preview_path"])

    if args.dry_run:
        print("\n[run] --dry-run activado: no se envio el correo.")
    else:
        print(f"\n[run] resultado envio: {result.get('send_result', '(sin send_result)')}")

    print(f"[run] run_id: {result.get('run_id')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
