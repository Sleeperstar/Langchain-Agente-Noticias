"""Renders a sample newsletter preview from fixture data (no API / LLM / network calls).

Builds the card PNGs with the branded placeholder background + company badge
(`card_images.compose_card`) and writes `output/sample_preview.html` with every
image embedded as a data URI, for visual review of the template.

    uv run python scripts/render_sample.py
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agente_noticias.card_images import (  # noqa: E402
    card_filename,
    compose_card,
    placeholder_image,
    save_card_png,
)
from agente_noticias.config import OUTPUT_DIR  # noqa: E402
from agente_noticias.email_template import render_email  # noqa: E402
from agente_noticias.schemas import (  # noqa: E402
    Article,
    ArticleEvaluation,
    Briefing,
    EvaluatedArticle,
)

SAMPLE_PATH = OUTPUT_DIR / "sample_preview.html"
SAMPLE_CARDS_DIR = OUTPUT_DIR / "sample_cards"

# Fictional but realistic items (example.com links on purpose).
NEWS = [
    {
        "company": "openai",
        "category": "Herramientas y productos",
        "label_es": "Lanzamiento",
        "title_es": "OpenAI quiere que ChatGPT haga tus compras por ti",
        "summary_es": (
            "ChatGPT ahora puede buscar, comparar y pagar productos en tiendas aliadas sin "
            "salir del chat. Comprar podría volverse tan fácil como mandar un mensaje."
        ),
        "title": "OpenAI launches agentic checkout in ChatGPT",
    },
    {
        "company": "google",
        "category": "Herramientas y productos",
        "label_es": "Herramientas",
        "title_es": "Gemini ya resume tus reuniones de Meet en segundos",
        "summary_es": (
            "Google activó resúmenes automáticos con tareas y responsables al terminar cada "
            "videollamada. Adiós a tomar notas a mano: la IA se encarga del acta."
        ),
        "title": "Gemini in Meet now writes meeting notes and action items",
    },
    {
        "company": "anthropic",
        "category": "IA agentica",
        "label_es": "Agentes",
        "title_es": "Claude aprende a usar la computadora como una persona",
        "summary_es": (
            "Anthropic mejoró su agente para que abra programas, llene formularios y ordene "
            "archivos por su cuenta. ¿Tu próximo compañero de oficina será una IA?"
        ),
        "title": "Anthropic upgrades Claude computer use",
    },
    {
        "company": "meta",
        "category": "Nuevos modelos",
        "label_es": "Modelo abierto",
        "title_es": "Meta libera gratis un modelo que compite con los grandes",
        "summary_es": (
            "El nuevo Llama se puede descargar y usar sin pagar licencias, incluso en "
            "empresas. Más competencia suele traer herramientas más baratas para todos."
        ),
        "title": "Meta releases new open-weights Llama model",
    },
    {
        "company": "nvidia",
        "category": "Industria",
        "label_es": "Negocios",
        "title_es": "NVIDIA presenta un chip que hace la IA más rápida y barata",
        "summary_es": (
            "Su nuevo procesador promete respuestas el doble de rápidas usando menos energía. "
            "Eso significa asistentes más ágiles en tu celular y en el trabajo."
        ),
        "title": "NVIDIA unveils next-generation inference chip",
    },
]

BRIEFING = Briefing(
    headline=f"La IA ya no solo conversa: ahora hace tareas - {date.today().isoformat()}",
    concepto_titulo="¿Qué es un agente de IA?",
    concepto_explicacion=(
        "Es una IA que no solo responde preguntas, sino que también hace tareas por ti, "
        "como agendar una reunión. Piensa en un asistente que sigue tus instrucciones "
        "paso a paso."
    ),
    chiste=(
        "¿Por qué la IA nunca llega tarde a la oficina? Porque siempre va un paso adelante "
        "con sus predicciones."
    ),
)


def build_items(cards_dir: Path = SAMPLE_CARDS_DIR) -> list[EvaluatedArticle]:
    cards_dir.mkdir(parents=True, exist_ok=True)
    items: list[EvaluatedArticle] = []
    for i, n in enumerate(NEWS, start=1):
        url = f"https://example.com/noticias-ia/{i}"
        out = cards_dir / card_filename(n["title"], url)
        save_card_png(compose_card(placeholder_image(seed=url), n["company"]), out)
        items.append(
            EvaluatedArticle(
                article=Article(title=n["title"], url=url, source="example.com"),
                evaluation=ArticleEvaluation(
                    reasoning="Sample.",
                    relevance_score=10 - i,
                    category=n["category"],
                    company=n["company"],
                    visual_subject="",
                    label_es=n["label_es"],
                    title_es=n["title_es"],
                    summary_es=n["summary_es"],
                ),
                card_image_path=str(out),
            )
        )
    return items


def main() -> int:
    html = render_email(BRIEFING, build_items(), "sample", "sample", "", images="data")
    SAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SAMPLE_PATH.write_text(html, encoding="utf-8")
    print(SAMPLE_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
