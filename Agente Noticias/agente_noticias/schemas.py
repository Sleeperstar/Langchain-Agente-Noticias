"""Esquemas Pydantic para salidas estructuradas del LLM."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CategoriaIA = Literal[
    "Nuevos modelos",
    "IA agentica",
    "Herramientas y productos",
    "Investigacion",
    "Industria",
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
    """Evaluacion del LLM para una noticia, pensada para una audiencia general."""

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
            "Que tan importante/interesante es la noticia para una audiencia general "
            "interesada en IA (0-10). Usa todo el rango, no concentres todo en 8-9."
        ),
    )
    category: CategoriaIA = Field(
        ...,
        description="Categoria principal de la noticia.",
    )
    summary_es: str = Field(
        ...,
        description="Resumen en espanol, 2-3 frases, claro y sin marketing.",
    )
    en_simple: str = Field(
        ...,
        description=(
            "Explicacion en lenguaje MUY sencillo (1-2 frases) para alguien sin "
            "conocimientos tecnicos: que es y por que deberia importarle. Sin jerga."
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
            "mas trascendente de la semana llega a 10."
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


class ConceptOut(BaseModel):
    """Salida estructurada para (re)generar el 'concepto del dia'."""

    concepto_titulo: str = Field(
        ...,
        description='Titulo del concepto en forma de pregunta (p. ej. "Que es Markdown?").',
    )
    concepto_explicacion: str = Field(
        ...,
        description=(
            "Explicacion SUPER simple en 2-3 frases para principiantes, con un "
            "ejemplo cotidiano si ayuda."
        ),
    )


class JokeOut(BaseModel):
    """Salida estructurada para (re)generar solo el chiste."""

    chiste: str = Field(
        ...,
        description=(
            "Un chiste corto y ligero sobre IA/tecnologia, en tono fresco y amigable "
            "(sin lisuras, sin temas sensibles, sin politica ni religion)."
        ),
    )


class BriefingText(BaseModel):
    """Textos del briefing SIN el chiste (para refrescar al editar noticias)."""

    headline: str = Field(..., description="Titulo principal del briefing.")
    tldr: list[str] = Field(
        ..., description="3 bullets ejecutivos en espanol (lectura de 30 segundos)."
    )
    concepto_titulo: str = Field(
        default="", description='Titulo del "concepto del dia".'
    )
    concepto_explicacion: str = Field(
        default="", description="Explicacion del concepto del dia (2-3 frases simples)."
    )


class Briefing(BaseModel):
    """Briefing consolidado para el correo."""

    headline: str = Field(..., description="Titulo principal del briefing.")
    tldr: list[str] = Field(
        ..., description="3 bullets ejecutivos en espanol (lectura de 30 segundos)."
    )
    concepto_titulo: str = Field(
        default="",
        description='Titulo del "concepto del dia" (p. ej. "Que es Markdown?").',
    )
    concepto_explicacion: str = Field(
        default="",
        description=(
            "Explicacion del concepto del dia en 2-3 frases, en lenguaje sencillo para "
            "principiantes."
        ),
    )
    chiste: str = Field(
        default="",
        description=(
            "Un chiste corto y ligero sobre IA/tecnologia, en tono fresco y amigable "
            "(sin lisuras, sin temas sensibles), para cerrar el correo con personalidad."
        ),
    )
