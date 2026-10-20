"""Configuracion centralizada: contexto, queries Tavily y parametros.

Este agente arma un boletin SEMANAL de noticias de IA generales y digeribles
para todo el equipo de WIN Internet (no tecnico), con el look and feel de la
marca. No esta enfocado en telecomunicaciones.
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

# Local SQLite history (anti-repetition). Card images live as files next to it.
DATA_DIR = PROJECT_DIR / "data"
DEFAULT_DB_PATH = DATA_DIR / "agente_noticias.db"
# Generated newsletter card PNGs: <DATA_DIR>/images/<YYYY-MM-DD>/<slug>.png
CARD_IMAGES_DIR = DATA_DIR / "images"

# Logo de Win para el header del correo (blanco + claim, PNG transparente).
ASSETS_DIR = PACKAGE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "win_logo.png"
# Company logos for the card badge: <key>.png (transparent, ~128 px tall).
COMPANY_LOGOS_DIR = ASSETS_DIR / "logos"

DEFAULT_RECIPIENT = "jquispeh@win.pe"
# Text LLM (OpenRouter model id; every chat call goes through OpenRouter, see llm.py).
DEFAULT_MODEL = "openai/gpt-5-mini"
DEFAULT_PROJECT = "agente-noticias-win"
# Card illustrations via OpenRouter's image API (verified available 2026-10-20).
DEFAULT_IMAGE_MODEL = "openai/gpt-image-2"
DEFAULT_IMAGE_QUALITY = "medium"


def load_environment() -> None:
    """Carga el .env propio del proyecto y activa el tracing de LangSmith."""
    if LOCAL_ENV.exists():
        load_dotenv(LOCAL_ENV, override=True)

    os.environ.setdefault("LANGSMITH_TRACING", "true")
    os.environ["LANGSMITH_PROJECT"] = os.getenv(
        "LANGSMITH_PROJECT_OVERRIDE", DEFAULT_PROJECT
    )

    # Alias por compatibilidad: algunas versiones de langchain leen las variables
    # con prefijo LANGCHAIN_ en vez de LANGSMITH_. Las dejamos sincronizadas para
    # asegurar que las trazas (tokens y costo) caigan en el proyecto correcto.
    os.environ["LANGCHAIN_TRACING_V2"] = os.environ["LANGSMITH_TRACING"]
    os.environ["LANGCHAIN_PROJECT"] = os.environ["LANGSMITH_PROJECT"]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# Audience: every WIN employee (all areas), mostly non-technical.
AUDIENCE_CONTEXT = """
La audiencia es TODO el equipo de WIN Internet (una empresa peruana de internet por
fibra optica): personas de todas las areas (ventas, atencion al cliente, operaciones,
tecnologia, administracion). La mayoria NO es experta en IA. Quieren enterarse en
pocos minutos, desde el celular, de lo mas importante del mundo de la inteligencia
artificial, de forma CORTA, clara y entretenida, sin sentirse abrumadas.

Les interesa sobre todo:
- Nuevos modelos y lanzamientos de las grandes (OpenAI, Google, Anthropic, Meta, etc.).
- IA agentica y asistentes que "hacen cosas" por si solos.
- Herramientas y productos de IA que cualquiera puede usar o que marcan tendencia.
- Hitos o noticias de la industria que dan tema de conversacion.

Evita la jerga. Si usas un termino tecnico, explicalo en simple.
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
# Below this many selected articles the newsletter is NOT sent (never email an empty one).
MIN_ARTICLES_TO_SEND = 1
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
    """OpenRouter model id. Legacy bare OpenAI ids (e.g. `gpt-5-mini`) get the `openai/` prefix."""
    model = os.getenv("NEWS_MODEL", "").strip() or DEFAULT_MODEL
    return model if "/" in model else f"openai/{model}"


def get_db_path() -> Path:
    """Path of the SQLite history DB (NEWS_DB_PATH, relative to the project if not absolute)."""
    raw = os.getenv("NEWS_DB_PATH", "").strip()
    if not raw:
        return DEFAULT_DB_PATH
    path = Path(raw).expanduser()
    return path if path.is_absolute() else PROJECT_DIR / path


def get_image_model() -> str:
    """OpenRouter model used for the card illustrations (NEWS_IMAGE_MODEL)."""
    return os.getenv("NEWS_IMAGE_MODEL", "").strip() or DEFAULT_IMAGE_MODEL


def get_image_quality() -> str:
    """Image quality tier sent to OpenRouter (NEWS_IMAGE_QUALITY: low|medium|high|auto)."""
    return os.getenv("NEWS_IMAGE_QUALITY", "").strip() or DEFAULT_IMAGE_QUALITY


def images_enabled() -> bool:
    """NEWS_IMAGES_ENABLED (default true). False skips AI generation (og:image/placeholder only)."""
    raw = os.getenv("NEWS_IMAGES_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}
