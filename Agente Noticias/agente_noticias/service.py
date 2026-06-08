"""Servicio de aplicacion: orquesta el borrador editable del briefing.

Reutiliza los nodos del grafo pero permite un flujo interactivo (human-in-the-loop)
para la interfaz web: generar borrador (con progreso en vivo), cambiar noticias
(automatico o por tema), regenerar el chiste y enviar.

Mantiene UN borrador en memoria (herramienta local de un solo usuario).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Iterator

from langchain.chat_models import init_chat_model
from langsmith import traceable

from agente_noticias.concepts import (
    generate_concept,
    get_recent_concepts,
    normalize_concept,
)
from agente_noticias.config import (
    DEDUP_WEEKS,
    DEFAULT_PROJECT,
    LOGO_PATH,
    MIN_RELEVANCE_SCORE,
    get_model,
    get_recipients,
)
from agente_noticias.db import fetch_recent_sent, save_briefing
from agente_noticias.email_template import logo_data_uri, render_email
from agente_noticias.jokes import (
    generate_unique_joke,
    get_recent_jokes,
    normalize_joke,
)
from agente_noticias.nodes.evaluator import _evaluate_one
from agente_noticias.nodes.researcher import _run_single_query
from agente_noticias.nodes.summarizer import _format_articles_block
from agente_noticias.prompts import SUMMARIZER_SYSTEM, SUMMARIZER_USER_TEMPLATE
from agente_noticias.schemas import Article, Briefing, BriefingText, EvaluatedArticle
from agente_noticias.text_utils import is_near_duplicate, normalize_title

# Nodos que se muestran en el visor de flujo en vivo (build_graph send=False).
DRAFT_NODES = [
    "researcher",
    "history_filter",
    "evaluator",
    "ranker",
    "summarizer",
    "email_writer",
]


@dataclass
class Draft:
    """Borrador actual del briefing en edicion."""

    selected: list[EvaluatedArticle] = field(default_factory=list)
    pool: list[EvaluatedArticle] = field(default_factory=list)
    briefing: Briefing | None = None
    run_id: str = ""


_DRAFT: Draft | None = None


def current_draft() -> Draft | None:
    return _DRAFT


# --------------------------------------------------------------------------- #
# Serializacion para la API
# --------------------------------------------------------------------------- #
def _serialize_article(item: EvaluatedArticle, index: int) -> dict:
    a, e = item.article, item.evaluation
    return {
        "index": index,
        "title": a.title,
        "url": a.url,
        "source": a.source,
        "published_date": a.published_date,
        "category": e.category,
        "relevance_score": e.relevance_score,
        "summary_es": e.summary_es,
        "en_simple": e.en_simple,
    }


def serialize_draft() -> dict:
    if _DRAFT is None or _DRAFT.briefing is None:
        return {"ready": False}
    b = _DRAFT.briefing
    return {
        "ready": True,
        "run_id": _DRAFT.run_id,
        "headline": b.headline,
        "tldr": b.tldr,
        "concepto_titulo": b.concepto_titulo,
        "concepto_explicacion": b.concepto_explicacion,
        "chiste": b.chiste,
        "pool_remaining": len(_DRAFT.pool),
        "articles": [
            _serialize_article(it, i) for i, it in enumerate(_DRAFT.selected)
        ],
    }


# --------------------------------------------------------------------------- #
# Generacion del borrador con progreso en vivo
# --------------------------------------------------------------------------- #
def stream_generate() -> Iterator[dict]:
    """Corre el grafo (send=False) y va emitiendo el progreso por nodo.

    Yields dicts: {"type": "node", "node": <nombre>, "status": "done"} y al final
    {"type": "done", "draft": <serializado>}.
    """
    global _DRAFT
    from agente_noticias.graph import build_graph, default_config

    graph = build_graph(send=False)
    config = default_config(thread_id=f"webapp-{date.today().isoformat()}")

    final_state: dict = {}
    yield {"type": "start", "nodes": DRAFT_NODES}
    try:
        for chunk in graph.stream({}, config, stream_mode="updates"):
            for node_name, update in chunk.items():
                if isinstance(update, dict):
                    final_state.update(update)
                yield {"type": "node", "node": node_name, "status": "done"}
    except Exception as exc:  # noqa: BLE001
        yield {"type": "error", "message": str(exc)}
        return

    selected: list[EvaluatedArticle] = final_state.get("selected_articles", []) or []
    scored: list[EvaluatedArticle] = final_state.get("scored_articles", []) or []
    briefing: Briefing | None = final_state.get("briefing")

    selected_urls = {it.article.url for it in selected}
    pool = [
        s
        for s in sorted(
            scored,
            key=lambda s: (s.evaluation.relevance_score, s.article.score),
            reverse=True,
        )
        if s.article.url not in selected_urls
        and s.evaluation.relevance_score >= MIN_RELEVANCE_SCORE
    ]

    _DRAFT = Draft(
        selected=selected,
        pool=pool,
        briefing=briefing,
        run_id=final_state.get("run_id", ""),
    )
    yield {"type": "done", "draft": serialize_draft()}


# --------------------------------------------------------------------------- #
# Refresco de los textos del briefing (sin tocar el chiste)
# --------------------------------------------------------------------------- #
def _refresh_briefing_text() -> None:
    """Regenera headline/TLDR/concepto a partir del set actual, conservando el chiste."""
    if _DRAFT is None or _DRAFT.briefing is None or not _DRAFT.selected:
        return
    llm = init_chat_model(get_model()).with_structured_output(BriefingText)
    user = SUMMARIZER_USER_TEMPLATE.format(
        articles_block=_format_articles_block(_DRAFT.selected),
        recent_jokes_block="(no aplica)",
    )
    try:
        txt: BriefingText = llm.invoke(
            [
                {"role": "system", "content": SUMMARIZER_SYSTEM},
                {"role": "user", "content": user},
            ]
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[service] no se pudo refrescar textos: {exc}")
        return

    today = date.today().isoformat()
    headline = txt.headline if today in txt.headline else f"{txt.headline} - {today}"
    _DRAFT.briefing = Briefing(
        headline=headline,
        tldr=txt.tldr[:3],
        concepto_titulo=txt.concepto_titulo,
        concepto_explicacion=txt.concepto_explicacion,
        chiste=_DRAFT.briefing.chiste,
    )


def _current_norm_titles(exclude_index: int | None = None) -> list[str]:
    titles = []
    for i, it in enumerate(_DRAFT.selected):  # type: ignore[union-attr]
        if exclude_index is not None and i == exclude_index:
            continue
        titles.append(normalize_title(it.article.title))
    return titles


# --------------------------------------------------------------------------- #
# Edicion de noticias
# --------------------------------------------------------------------------- #
@traceable(name="regenerar_noticia_auto", run_type="chain")
def regenerate_article_auto(index: int) -> dict:
    """Cambia la noticia `index` por el siguiente mejor candidato del pool."""
    if _DRAFT is None or not (0 <= index < len(_DRAFT.selected)):
        return {"ok": False, "error": "indice invalido o sin borrador"}

    other_titles = _current_norm_titles(exclude_index=index)
    other_urls = {
        it.article.url for i, it in enumerate(_DRAFT.selected) if i != index
    }

    replacement = None
    for cand in list(_DRAFT.pool):
        norm = normalize_title(cand.article.title)
        if cand.article.url in other_urls or is_near_duplicate(norm, other_titles):
            continue
        replacement = cand
        break

    if replacement is None:
        return {"ok": False, "error": "no quedan candidatos alternativos; usa busqueda por tema"}

    _DRAFT.pool.remove(replacement)
    # La noticia saliente vuelve al pool por si se quiere recuperar luego.
    _DRAFT.pool.append(_DRAFT.selected[index])
    _DRAFT.selected[index] = replacement

    _refresh_briefing_text()
    return {"ok": True, "draft": serialize_draft()}


@traceable(name="reemplazar_noticia_por_tema", run_type="chain")
def replace_article_by_topic(index: int, topic: str) -> dict:
    """Busca `topic` en Tavily y reemplaza la noticia `index` con el mejor resultado."""
    if _DRAFT is None or not (0 <= index < len(_DRAFT.selected)):
        return {"ok": False, "error": "indice invalido o sin borrador"}
    topic = (topic or "").strip()
    if not topic:
        return {"ok": False, "error": "escribe un tema"}

    spec = {
        "query": topic,
        "topic": "news",
        "search_depth": "advanced",
        "max_results": 8,
        "time_range": "month",
    }
    try:
        results: list[Article] = _run_single_query(spec)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"fallo la busqueda: {exc}"}

    if not results:
        return {"ok": False, "error": "no se encontraron resultados para ese tema"}

    # Evitar duplicados con la seleccion actual y con el historial enviado.
    other_titles = _current_norm_titles(exclude_index=index)
    other_urls = {
        it.article.url for i, it in enumerate(_DRAFT.selected) if i != index
    }
    sent = fetch_recent_sent(DEDUP_WEEKS)
    sent_urls = {r.get("url", "") for r in sent if r.get("url")}
    sent_titles = [r.get("normalized_title", "") for r in sent if r.get("normalized_title")]

    candidate_article = None
    for art in sorted(results, key=lambda x: x.score, reverse=True):
        norm = normalize_title(art.title)
        if art.url in other_urls or art.url in sent_urls:
            continue
        if is_near_duplicate(norm, other_titles) or is_near_duplicate(norm, sent_titles):
            continue
        candidate_article = art
        break

    if candidate_article is None:
        return {"ok": False, "error": "los resultados ya estaban repetidos; prueba otro tema"}

    evaluated = _evaluate_one(candidate_article)
    if evaluated is None:
        return {"ok": False, "error": "no se pudo evaluar la noticia encontrada"}

    _DRAFT.pool.append(_DRAFT.selected[index])
    _DRAFT.selected[index] = evaluated

    _refresh_briefing_text()
    return {"ok": True, "draft": serialize_draft()}


@traceable(name="regenerar_chiste", run_type="chain")
def regenerate_joke() -> dict:
    """Genera un chiste nuevo (anti-repeticion contra la BD y el actual)."""
    if _DRAFT is None or _DRAFT.briefing is None:
        return {"ok": False, "error": "sin borrador"}
    recent = get_recent_jokes()
    current = _DRAFT.briefing.chiste
    nuevo = generate_unique_joke(recent=recent, avoid=[current] if current else None)
    if not nuevo:
        return {"ok": False, "error": "no se pudo generar un chiste nuevo"}
    _DRAFT.briefing.chiste = nuevo
    return {"ok": True, "chiste": nuevo}


def _news_context_for_concept() -> str:
    """Pequeno contexto con los titulares actuales para inspirar el concepto."""
    if _DRAFT is None:
        return ""
    return "; ".join(it.article.title for it in _DRAFT.selected[:5])


@traceable(name="regenerar_concepto", run_type="chain")
def regenerate_concept() -> dict:
    """Genera un concepto del dia nuevo (anti-repeticion contra la BD y el actual)."""
    if _DRAFT is None or _DRAFT.briefing is None:
        return {"ok": False, "error": "sin borrador"}
    recent = get_recent_concepts()
    current = _DRAFT.briefing.concepto_titulo
    nuevo = generate_concept(
        recent=recent,
        avoid=[current] if current else None,
        news_context=_news_context_for_concept(),
    )
    if nuevo is None:
        return {"ok": False, "error": "no se pudo generar un concepto nuevo"}
    _DRAFT.briefing.concepto_titulo = nuevo.concepto_titulo
    _DRAFT.briefing.concepto_explicacion = nuevo.concepto_explicacion
    return {
        "ok": True,
        "concepto_titulo": nuevo.concepto_titulo,
        "concepto_explicacion": nuevo.concepto_explicacion,
    }


@traceable(name="concepto_personalizado", run_type="chain")
def set_custom_concept(topic: str) -> dict:
    """Genera el concepto del dia sobre el tema que pide el usuario."""
    if _DRAFT is None or _DRAFT.briefing is None:
        return {"ok": False, "error": "sin borrador"}
    topic = (topic or "").strip()
    if not topic:
        return {"ok": False, "error": "escribe un concepto o tema"}
    nuevo = generate_concept(topic=topic, news_context=_news_context_for_concept())
    if nuevo is None:
        return {"ok": False, "error": "no se pudo generar el concepto"}
    _DRAFT.briefing.concepto_titulo = nuevo.concepto_titulo
    _DRAFT.briefing.concepto_explicacion = nuevo.concepto_explicacion
    return {
        "ok": True,
        "concepto_titulo": nuevo.concepto_titulo,
        "concepto_explicacion": nuevo.concepto_explicacion,
    }


# --------------------------------------------------------------------------- #
# Preview y envio
# --------------------------------------------------------------------------- #
def render_preview() -> str:
    """HTML del correo para el iframe (logo embebido como data URI)."""
    if _DRAFT is None or _DRAFT.briefing is None:
        return "<p style='font-family:sans-serif;padding:24px;'>Aun no hay borrador.</p>"
    return render_email(
        briefing=_DRAFT.briefing,
        selected=_DRAFT.selected,
        model=get_model(),
        project=os.getenv("LANGSMITH_PROJECT", DEFAULT_PROJECT),
        run_id=_DRAFT.run_id,
        logo_src=logo_data_uri(),
    )


@traceable(name="enviar_correo", run_type="chain")
def send_now() -> dict:
    """Renderiza con CID, envia por Outlook y persiste el historial (un solo envio)."""
    if _DRAFT is None or _DRAFT.briefing is None or not _DRAFT.selected:
        return {"ok": False, "error": "sin borrador para enviar"}

    from agente_noticias.nodes.outlook_sender import _send_via_outlook

    briefing = _DRAFT.briefing
    subject = briefing.headline
    model = get_model()
    project = os.getenv("LANGSMITH_PROJECT", DEFAULT_PROJECT)

    html = render_email(
        briefing=briefing,
        selected=_DRAFT.selected,
        model=model,
        project=project,
        run_id=_DRAFT.run_id,
        logo_src="cid:winlogo" if LOGO_PATH.exists() else "",
    )

    recipients = get_recipients()
    try:
        result = _send_via_outlook("; ".join(recipients), subject, html)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"fallo el envio: {exc}"}

    briefing_id = ""
    if "enviado" in result.lower():
        articles = []
        for it in _DRAFT.selected:
            a, e = it.article, it.evaluation
            articles.append(
                {
                    "url": a.url,
                    "normalized_title": normalize_title(a.title),
                    "title": a.title,
                    "source": a.source,
                    "category": e.category,
                    "relevance_score": e.relevance_score,
                    "published_date": a.published_date,
                }
            )
        briefing_id = save_briefing(
            subject=subject,
            recipients=", ".join(recipients),
            run_id=_DRAFT.run_id,
            langsmith_project=project,
            articles=articles,
            joke=briefing.chiste,
            joke_normalized=normalize_joke(briefing.chiste),
            concepto_titulo=briefing.concepto_titulo,
            concepto_explicacion=briefing.concepto_explicacion,
            concepto_normalized=normalize_concept(briefing.concepto_titulo),
        )

    return {
        "ok": True,
        "result": result,
        "briefing_id": briefing_id,
        "recipients": recipients,
    }
