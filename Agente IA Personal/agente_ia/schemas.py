"""Esquemas Pydantic para salidas estructuradas del LLM."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CategoriaIA = Literal[
    "Nuevos modelos (LLMs/Multimodal)",
    "IA agentica y agentes",
    "Frameworks y tooling",
    "Research y papers",
    "Industria y carrera",
]


class Article(BaseModel):
    """Articulo crudo devuelto por Tavily, normalizado."""

    title: str
    url: str
    content: str = ""
    source: str = ""
    published_date: str = ""
    score: float = 0.0
    query: str = ""


class ArticleEvaluation(BaseModel):
    """Evaluacion del LLM para una noticia, desde la perspectiva de un AI Engineer."""

    reasoning: str = Field(
        ...,
        description=(
            "Breve justificacion (1 frase) ANTES de puntuar: que tipo de noticia es "
            "y por que merece el score que le vas a dar."
        ),
    )
    relevance_score: int = Field(
        ...,
        ge=0,
        le=10,
        description=(
            "Relevancia para un AI Engineer interesado en nuevos modelos e IA "
            "agentica (0-10). Usa todo el rango, no concentres todo en 8-9."
        ),
    )
    category: CategoriaIA = Field(
        ...,
        description="Categoria principal de la noticia.",
    )
    summary_es: str = Field(
        ...,
        description=(
            "Resumen en espanol, 2-3 frases, claro y sin marketing. Manten los "
            "terminos tecnicos en ingles (p. ej. 'context window', 'tool calling')."
        ),
    )
    why_relevant: str = Field(
        ...,
        description=(
            "Por que le importa a alguien que quiere ser AI Engineer (1-2 frases, "
            "en espanol)."
        ),
    )
    what_to_learn: str = Field(
        ...,
        description=(
            "Un concepto, skill o herramienta concreta a explorar a partir de esta "
            "noticia (frase corta; nombres tecnicos en ingles)."
        ),
    )


class EvaluatedArticle(BaseModel):
    article: Article
    evaluation: ArticleEvaluation


class RankedSelection(BaseModel):
    """Una noticia seleccionada por el ranker comparativo."""

    index: int = Field(
        ...,
        ge=1,
        description="Indice (1-based) del articulo en la lista de candidatos.",
    )
    final_score: int = Field(
        ...,
        ge=1,
        le=10,
        description=(
            "Importancia relativa DIFERENCIADA (1-10). Evita empates: solo la noticia "
            "mas trascendente del dia llega a 10."
        ),
    )
    rationale: str = Field(
        default="",
        description="Una linea: por que esta noticia merece esta posicion/score.",
    )


class Ranking(BaseModel):
    """Resultado del ranker: las noticias mas importantes, ordenadas y diferenciadas."""

    selected: list[RankedSelection] = Field(
        ...,
        description=(
            "Las noticias mas importantes y DISTINTAS (sin duplicados del mismo evento), "
            "ordenadas de mayor a menor importancia, con scores diferenciados."
        ),
    )


class Briefing(BaseModel):
    """Briefing consolidado para el correo."""

    headline: str = Field(..., description="Titulo principal del briefing (espanol).")
    tldr: list[str] = Field(
        ...,
        description="Exactamente 3 bullets ejecutivos en espanol (lectura de 30 segundos).",
    )
    skill_of_the_day: str = Field(
        ...,
        description=(
            "Una recomendacion concreta de skill/concepto para estudiar hoy, derivada "
            "de las noticias (1 frase; terminos tecnicos en ingles)."
        ),
    )
