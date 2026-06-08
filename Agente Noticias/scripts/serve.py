"""Levanta la interfaz web del Agente Noticias IA (Win) y abre el navegador.

Uso:
    uv run python scripts/serve.py            # http://127.0.0.1:8800
    uv run python scripts/serve.py --port 8900
    uv run python scripts/serve.py --no-browser
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Interfaz web Agente Noticias IA - Win")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8800)
    p.add_argument("--no-browser", action="store_true", help="No abrir el navegador.")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    import agente_noticias  # noqa: F401  (carga .env)
    import uvicorn

    url = f"http://{args.host}:{args.port}"
    print(f"[serve] Interfaz web en {url}")

    if not args.no_browser:
        def _open():
            time.sleep(1.2)
            try:
                webbrowser.open(url)
            except Exception:  # noqa: BLE001
                pass

        threading.Thread(target=_open, daemon=True).start()

    uvicorn.run("agente_noticias.webapp.app:app", host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
