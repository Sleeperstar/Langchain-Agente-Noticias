"""Configuracion centralizada: contexto Win Internet, queries Tavily y parametros."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
WORKSPACE_DIR = PROJECT_DIR.parent
COURSE_ENV = WORKSPACE_DIR / "lca-lc-foundations" / ".env"
LOCAL_ENV = PROJECT_DIR / ".env"

OUTPUT_DIR = PROJECT_DIR / "output"
PREVIEW_PATH = OUTPUT_DIR / "preview.html"

DEFAULT_RECIPIENT = "jquispeh@win.pe"
DEFAULT_MODEL = "gpt-5-nano"
DEFAULT_PROJECT = "agente-noticias-win"


def load_environment() -> None:
    """Carga primero el .env del curso y luego el local si existe.

    Tambien fuerza la activacion de tracing en LangSmith con el proyecto
    `agente-noticias-win` para que toda corrida quede en su propio bucket.
    """
    if COURSE_ENV.exists():
        load_dotenv(COURSE_ENV, override=False)
    if LOCAL_ENV.exists():
        load_dotenv(LOCAL_ENV, override=True)

    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ["LANGSMITH_PROJECT"] = os.getenv(
        "LANGSMITH_PROJECT_OVERRIDE", DEFAULT_PROJECT
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


WIN_CONTEXT = """
Win Internet (Win Empresas SAC) es una empresa peruana proveedora de servicios de
internet por fibra optica que opera principalmente en Lima y provincias del Peru.
Sus prioridades estrategicas son:
- Calidad y disponibilidad de la red de fibra optica (FTTH).
- Atencion al cliente y soporte tecnico (canales digitales y call center).
- Crecimiento de mercado frente a competidores: Movistar, Claro, Entel, Bitel.
- Cumplimiento regulatorio con OSIPTEL y MTC en Peru.
- Adopcion de IA para automatizar operaciones, ventas, soporte y deteccion de fraude.
""".strip()

IMPACT_AREAS = [
    "Operaciones y Red",
    "Atencion al Cliente",
    "Competencia",
    "Regulacion",
    "Mercado y Negocio",
]

# Queries para Tavily. Combinamos foco en IA aplicada a telecom, IA en Peru
# y movimientos de competidores/regulador.
SEARCH_QUERIES: list[dict] = [
    {
        "query": "IA inteligencia artificial telecom fibra optica ISP 2026",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 6,
        "time_range": "week",
    },
    {
        "query": "inteligencia artificial Peru telecomunicaciones operadores",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 6,
        "time_range": "week",
        "country": "peru",
    },
    {
        "query": "Movistar Claro Entel Bitel inteligencia artificial Peru",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 6,
        "time_range": "month",
        "country": "peru",
    },
    {
        "query": "OSIPTEL MTC Peru inteligencia artificial regulacion telecomunicaciones",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 6,
        "time_range": "month",
        "country": "peru",
    },
    {
        "query": "AI customer service fiber broadband ISP automation",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 6,
        "time_range": "week",
    },
]

MIN_RELEVANCE_SCORE = 6
MAX_ARTICLES_IN_EMAIL = 8


def get_recipient() -> str:
    return os.getenv("NEWS_RECIPIENT", DEFAULT_RECIPIENT)


def get_model() -> str:
    return os.getenv("NEWS_MODEL", DEFAULT_MODEL)
