"""Esquemas Pydantic para salidas estructuradas del LLM."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ImpactArea = Literal[
    "Operaciones y Red",
    "Atencion al Cliente",
    "Competencia",
    "Regulacion",
    "Mercado y Negocio",
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
    """Evaluacion del LLM para una noticia, desde la perspectiva de Win Internet."""

    relevance_score: int = Field(
        ...,
        ge=0,
        le=10,
        description="Que tan relevante es la noticia para Win Internet (0-10).",
    )
    impact_areas: list[ImpactArea] = Field(
        default_factory=list,
        description="Una o mas areas internas de Win Internet impactadas.",
    )
    summary_es: str = Field(
        ...,
        description="Resumen ejecutivo en espanol, 2-3 frases, sin marketing.",
    )
    why_matters_for_win: str = Field(
        ...,
        description="Explicacion concreta de por que importa a Win Internet (1-2 frases).",
    )


class EvaluatedArticle(BaseModel):
    article: Article
    evaluation: ArticleEvaluation


class Briefing(BaseModel):
    """Briefing consolidado para el correo."""

    headline: str = Field(..., description="Titulo principal del briefing.")
    tldr: list[str] = Field(
        ..., description="3 bullets ejecutivos en espanol (lectura de 30 segundos)."
    )
