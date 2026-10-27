"""Ejecuta el Agente Noticias IA (Win Internet) end-to-end.

Uso basico:

    uv run python scripts/run.py                  # busca, arma briefing y envia por Outlook
    uv run python scripts/run.py --dry-run        # preview + borrador (send_draft.py), NO envia
    uv run python scripts/run.py --headless       # no abre el navegador con el preview
    uv run python scripts/run.py --model openai/gpt-5-mini   # override (id de OpenRouter)
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
    parser = argparse.ArgumentParser(description="Agente Noticias IA - Win Internet")
    parser.add_argument("--dry-run", action="store_true",
                        help="Genera el preview HTML y un borrador listo para enviar con "
                             "scripts/send_draft.py, pero NO envia ni guarda historial.")
    parser.add_argument("--headless", action="store_true",
                        help="No abre el preview en el navegador.")
    parser.add_argument("--model", type=str, default=None,
                        help="Override del modelo LLM, id de OpenRouter (setea NEWS_MODEL).")
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

    import agente_noticias  # noqa: F401  (dispara load_environment)
    from agente_noticias.config import MIN_ARTICLES_TO_SEND, get_model, get_recipients
    from agente_noticias.graph import build_graph, default_config

    thread_id = args.thread or f"agente-noticias-{date.today().isoformat()}-{uuid.uuid4().hex[:6]}"
    config = default_config(thread_id=thread_id)
    print(f"[run] thread_id={thread_id}  project={os.getenv('LANGSMITH_PROJECT')}")
    print(f"[run] modelo={get_model()}  destinatarios={', '.join(get_recipients())}")

    graph = build_graph(send=not args.dry_run)
    result = graph.invoke({}, config)

    n_articles = len(result.get("selected_articles", []) or [])
    draft_path = None
    draft_error = None
    if args.dry_run and n_articles >= MIN_ARTICLES_TO_SEND:
        from agente_noticias.draft import save_draft

        try:
            draft_path = save_draft(result)
        except Exception as exc:  # noqa: BLE001 - disk/copy errors must not hide the preview
            draft_error = str(exc)

    briefing = result.get("briefing")
    print("\n=== Briefing generado ===")
    if briefing is not None:
        print(f"Asunto:           {result.get('subject')}")
        print(f"Archivo preview:  {result.get('preview_path')}")
        if draft_path is not None:
            print(f"Borrador envio:   {draft_path}")
        print(f"Articulos:        {len(result.get('selected_articles', []) or [])}")
        print(f"Descartadas hist: {result.get('dropped_by_history', 0)}")
        print("Noticias:")
        for item in result.get("selected_articles", []) or []:
            print(f"  - {item.evaluation.title_es or item.article.title}")
        if briefing.concepto_titulo:
            print(f"Concepto del dia: {briefing.concepto_titulo}")

    if not args.headless and result.get("preview_path"):
        _open_preview(result["preview_path"])

    if args.dry_run:
        print("\n[run] --dry-run activado: no se envio ni se guardo historial.")
        if draft_path is not None:
            print("[run] revisa el preview y envia ESE borrador con:")
            print("      uv run python scripts/send_draft.py --to persona1@win.pe,persona2@win.pe")
    else:
        print(f"\n[run] resultado envio:  {result.get('send_result', '(sin send_result)')}")
        print(f"[run] briefing_id:      {result.get('briefing_id', '(no guardado)')}")

    print(f"[run] run_id: {result.get('run_id')}")
    if n_articles < MIN_ARTICLES_TO_SEND:
        # Both modes exit 1 so schedulers/operators notice an empty run.
        reason = result.get("send_result") or f"no se envio: {n_articles} noticias seleccionadas"
        print(f"[run] ERROR: boletin vacio, NO se envia ({reason}).", file=sys.stderr)
        return 1
    if draft_error is not None:
        print(f"[run] ERROR: no se pudo guardar el borrador: {draft_error}", file=sys.stderr)
        return 1
    if not args.dry_run and not result.get("send_ok"):
        print("[run] ERROR: el correo NO se envio (ver [outlook_sender]).", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
