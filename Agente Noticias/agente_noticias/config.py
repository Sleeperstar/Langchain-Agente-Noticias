"""Configuracion centralizada: contexto, queries Tavily y parametros.

Este agente arma un briefing SEMANAL de noticias de IA generales y digeribles
para los directivos de Win Internet (nivel inicial/intermedio), con el look and
feel de la marca. No esta enfocado en telecomunicaciones.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = PACKAGE_DIR.parent
WORKSPACE_DIR = PROJECT_DIR.parent
LOCAL_ENV = PROJECT_DIR / ".env"

OUTPUT_DIR = PROJECT_DIR / "output"
PREVIEW_PATH = OUTPUT_DIR / "preview.html"

# Logo de Win para el header del correo (blanco + claim, PNG transparente).
ASSETS_DIR = PACKAGE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "win_logo.png"

DEFAULT_RECIPIENT = "jquispeh@win.pe"
DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_PROJECT = "agente-noticias-win"


def load_environment() -> None:
    """Carga el .env propio del proyecto y activa el tracing de LangSmith."""
    if LOCAL_ENV.exists():
        load_dotenv(LOCAL_ENV, override=True)

    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ["LANGSMITH_PROJECT"] = os.getenv(
        "LANGSMITH_PROJECT_OVERRIDE", DEFAULT_PROJECT
    )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Contexto de audiencia: directivos de Win con nivel inicial/intermedio en IA.
AUDIENCE_CONTEXT = """
La audiencia son directivos y gerentes de Win Internet (una empresa peruana de
internet por fibra optica). NO son expertos en IA: tienen un nivel inicial o
intermedio. Quieren mantenerse al dia con las novedades mas importantes del mundo
de la inteligencia artificial de forma DIGERIBLE y entretenida, no tecnica.

Les interesa sobre todo:
- Nuevos modelos y lanzamientos de las grandes (OpenAI, Google, Anthropic, Meta, etc.).
- IA agentica y asistentes que "hacen cosas" por si solos.
- Herramientas y productos de IA que cualquiera puede usar o que marcan tendencia.
- Hitos o noticias de la industria que dan tema de conversacion.

Evita la jerga innecesaria. Si usas un termino tecnico, explicalo en simple.
""".strip()

# Categorias generales (deben coincidir con schemas.CategoriaIA).
CATEGORIAS = [
    "Nuevos modelos",
    "IA agentica",
    "Herramientas y productos",
    "Investigacion",
    "Industria",
]

# Dominios curados de alta senal para reforzar la calidad de las fuentes.
CURATED_DOMAINS = [
    "openai.com",
    "anthropic.com",
    "ai.googleblog.com",
    "deepmind.google",
    "blog.google",
    "ai.meta.com",
    "mistral.ai",
    "huggingface.co",
    "techcrunch.com",
    "venturebeat.com",
    "theverge.com",
    "arstechnica.com",
    "wired.com",
    "technologyreview.com",
]

# Queries para Tavily: foco en novedades de IA generales y digeribles.
SEARCH_QUERIES: list[dict] = [
    {
        "query": "new AI model release OpenAI Google Anthropic announcement",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 6,
        "time_range": "week",
    },
    {
        "query": "AI agents assistant new product launch",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 6,
        "time_range": "week",
    },
    {
        "query": "artificial intelligence news breakthrough this week",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 6,
        "time_range": "week",
        "include_domains": CURATED_DOMAINS,
    },
    {
        "query": "generative AI tool everyone is talking about",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 6,
        "time_range": "week",
    },
    {
        "query": "inteligencia artificial noticias novedades modelos",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 6,
        "time_range": "week",
    },
]

# Bar minima para considerar un articulo como candidato (el ranker diferencia).
MIN_RELEVANCE_SCORE = 5
# Cuantos candidatos pasan al ranker comparativo.
MAX_CANDIDATES = 12
# Cuantas noticias finales entran al briefing.
MAX_ARTICLES = 5
# Compatibilidad con codigo previo que usaba este nombre.
MAX_ARTICLES_IN_EMAIL = MAX_ARTICLES
# Umbral de similitud de titulo (0-1) para considerar dos noticias duplicadas.
TITLE_SIMILARITY_THRESHOLD = 0.8
# Semanas hacia atras a revisar en el historial para no repetir noticias.
DEDUP_WEEKS = int(os.getenv("DEDUP_WEEKS", "6"))


def get_recipient() -> str:
    return os.getenv("NEWS_RECIPIENT", DEFAULT_RECIPIENT)


def get_recipients() -> list[str]:
    """Lista de destinatarios (NEWS_RECIPIENT separado por comas)."""
    raw = get_recipient()
    return [r.strip() for r in raw.split(",") if r.strip()]


def get_model() -> str:
    return os.getenv("NEWS_MODEL", DEFAULT_MODEL)


def get_supabase_config() -> tuple[str, str]:
    """Devuelve (url, service_role_key) o ('', '') si no estan configuradas."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key or key.startswith("PENDIENTE"):
        return "", ""
    return url, key
