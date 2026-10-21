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

# Canonical company keys for the card logo badge (must match logos.COMPANY_DISPLAY_NAMES).
CompanyKey = Literal[
    "openai",
    "anthropic",
    "google",
    "gemini",
    "meta",
    "microsoft",
    "nvidia",
    "xai",
    "mistral",
    "deepseek",
    "apple",
    "amazon",
    "alibaba",
    "qwen",
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
    # Source image of the article (Tavily per-result image), if any.
    image_url: str | None = None


class ArticleEvaluation(BaseModel):
    """Evaluacion del LLM para una noticia, pensada para todo el equipo de WIN."""

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
    company: CompanyKey | None = Field(
        default=None,
        description=(
            "Empresa principal de la que trata la noticia, como clave canonica. Usa "
            "'gemini' si es sobre los modelos/app Gemini y 'google' para el resto de "
            "Google/DeepMind; 'qwen' para modelos Qwen y 'alibaba' para el resto de "
            "Alibaba. null si no es sobre una de estas empresas."
        ),
    )
    visual_subject: str = Field(
        default="",
        description=(
            "In ENGLISH, max 25 words: a visual metaphor that illustrates the news for an "
            "abstract editorial illustration. No brand names, logos, text or real people."
        ),
    )
    label_es: str = Field(
        ...,
        description=(
            "Etiqueta corta de la tarjeta en espanol (1-2 palabras, sin la empresa), "
            "p. ej. 'Lanzamiento', 'Herramientas', 'Agentes', 'Investigacion', 'Negocios'."
        ),
    )
    title_es: str = Field(
        ...,
        description=(
            "Titulo de la tarjeta en espanol: corto y llamativo (maximo ~70 caracteres), "
            "puede ser un poco provocador pero nunca exagerado ni falso."
        ),
    )
    summary_es: str = Field(
        ...,
        description=(
            "Resumen en espanol para todo el equipo: exactamente 2 frases, 20-30 palabras "
            "en total, en lenguaje sencillo y sin jerga; cierra con un gancho si es natural."
        ),
    )


class EvaluatedArticle(BaseModel):
    article: Article
    evaluation: ArticleEvaluation
    # Absolute path of the generated card PNG (set by the card_images node).
    card_image_path: str | None = None


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
            "Explicacion SUPER simple en maximo 3 frases cortas para cualquier persona, "
            "con un ejemplo cotidiano si ayuda."
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

    headline: str = Field(
        ..., description="Titular corto y atractivo del boletin (maximo ~60 caracteres)."
    )
    concepto_titulo: str = Field(
        default="", description='Titulo del "concepto del dia".'
    )
    concepto_explicacion: str = Field(
        default="",
        description="Explicacion del concepto del dia (maximo 3 frases cortas y simples).",
    )


class Briefing(BaseModel):
    """Briefing consolidado para el correo."""

    headline: str = Field(
        ..., description="Titular corto y atractivo del boletin (maximo ~60 caracteres)."
    )
    concepto_titulo: str = Field(
        default="",
        description='Titulo del "concepto del dia" (p. ej. "Que es Markdown?").',
    )
    concepto_explicacion: str = Field(
        default="",
        description=(
            "Explicacion del concepto del dia en maximo 3 frases cortas, en lenguaje "
            "sencillo para cualquier persona."
        ),
    )
    chiste: str = Field(
        default="",
        description=(
            "Un chiste corto y ligero sobre IA/tecnologia, en tono fresco y amigable "
            "(sin lisuras, sin temas sensibles), para cerrar el correo con personalidad."
        ),
    )
