"""Configuracion centralizada: contexto AI Engineer, queries Tavily y parametros."""
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

DEFAULT_RECIPIENT = "tu_correo@ejemplo.com"
DEFAULT_MODEL = "gpt-5-mini"
DEFAULT_PROJECT = "agente-ia-personal"


def load_environment() -> None:
    """Carga primero el .env del curso (si existe) y luego el local.

    Tambien fuerza el tracing de LangSmith con el proyecto `agente-ia-personal`
    para que toda corrida quede en su propio bucket.
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


AI_ENGINEER_CONTEXT = """
El lector es un profesional que aspira a convertirse en AI Engineer. Le interesa
mantenerse al dia con lo mas relevante del ecosistema de IA, con foco en:
- Nuevos modelos: lanzamientos de LLMs y modelos multimodales (frontier y open source),
  benchmarks, capacidades de razonamiento, ventanas de contexto y precios.
- IA agentica: agentes autonomos, multi-agente, tool use, planificacion, memoria,
  patrones de orquestacion (LangGraph, etc.) y casos de uso en produccion.
- Frameworks y tooling: LangChain, LangGraph, LlamaIndex, frameworks de evaluacion,
  vector stores, MCP y servidores de herramientas.
- Research y papers: avances que un AI Engineer deberia conocer aunque sea a alto nivel.
- Industria y carrera: movimientos de las empresas, adopcion, y skills demandadas.

Prioriza senal sobre ruido: novedades accionables y de impacto, no hype generico.
""".strip()

# Categorias para clasificar cada noticia (deben coincidir con schemas.CategoriaIA).
CATEGORIAS = [
    "Nuevos modelos (LLMs/Multimodal)",
    "IA agentica y agentes",
    "Frameworks y tooling",
    "Research y papers",
    "Industria y carrera",
]

# Dominios curados de alta senal para reforzar la calidad de las fuentes.
CURATED_DOMAINS = [
    "openai.com",
    "anthropic.com",
    "ai.googleblog.com",
    "deepmind.google",
    "ai.meta.com",
    "mistral.ai",
    "huggingface.co",
    "arxiv.org",
    "news.ycombinator.com",
    "blog.langchain.dev",
    "langchain.com",
    "techcrunch.com",
    "venturebeat.com",
    "theverge.com",
]

# Queries para Tavily. Combinamos busqueda abierta de noticias con consultas
# restringidas a dominios curados para subir la senal.
SEARCH_QUERIES: list[dict] = [
    {
        "query": "new LLM model release frontier model capabilities",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 6,
        "time_range": "week",
    },
    {
        "query": "agentic AI autonomous agents framework tool use",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 6,
        "time_range": "week",
    },
    {
        "query": "open source LLM release model weights benchmark",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 6,
        "time_range": "week",
        "include_domains": CURATED_DOMAINS,
    },
    {
        "query": "AI agents multi-agent orchestration LangGraph LangChain",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 6,
        "time_range": "month",
        "include_domains": CURATED_DOMAINS,
    },
    {
        "query": "new AI model reasoning multimodal benchmark state of the art",
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 6,
        "time_range": "week",
    },
]

# Bar minima para considerar un articulo como candidato (el ranker hace la
# diferenciacion final). La dejamos baja para no perder candidatos por el sesgo
# del evaluador a puntuar alto.
MIN_RELEVANCE_SCORE = 5
# Cuantos candidatos pasan al ranker comparativo.
MAX_CANDIDATES = 12
# Cuantas noticias finales entran al briefing.
MAX_ARTICLES = 5
# Umbral de similitud de titulo (0-1) para considerar dos noticias duplicadas.
TITLE_SIMILARITY_THRESHOLD = 0.8


def get_recipient() -> str:
    return os.getenv("NEWS_RECIPIENT", DEFAULT_RECIPIENT)


def get_model() -> str:
    return os.getenv("NEWS_MODEL", DEFAULT_MODEL)
