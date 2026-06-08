"""Backend FastAPI de la interfaz web del Agente Noticias IA (Win).

Sirve la SPA con look & feel de Win y expone la API para:
- generar el borrador con progreso en vivo (SSE),
- cambiar noticias (automatico o por tema),
- regenerar el chiste,
- previsualizar y enviar el correo.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import agente_noticias  # noqa: F401  -> carga .env y activa LangSmith
from agente_noticias import service
from agente_noticias.config import LOGO_PATH, get_recipients

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Agente Noticias IA - Win")


@app.middleware("http")
async def no_cache_static(request, call_next):
    """Evita que el navegador use copias viejas del HTML/CSS/JS (herramienta local)."""
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


class TopicBody(BaseModel):
    topic: str = ""


@app.get("/", response_class=HTMLResponse)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config")
def api_config() -> JSONResponse:
    return JSONResponse(
        {
            "recipients": get_recipients(),
            "nodes": service.DRAFT_NODES,
            "has_logo": LOGO_PATH.exists(),
        }
    )


@app.get("/api/logo")
def api_logo():
    if LOGO_PATH.exists():
        return FileResponse(LOGO_PATH, media_type="image/png")
    return JSONResponse({"error": "no logo"}, status_code=404)


@app.get("/api/generate/stream")
def api_generate_stream() -> StreamingResponse:
    """SSE: emite el progreso por nodo y, al final, el borrador serializado."""

    def event_stream():
        for evt in service.stream_generate():
            yield f"data: {json.dumps(evt, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/draft")
def api_draft() -> JSONResponse:
    return JSONResponse(service.serialize_draft())


@app.get("/api/preview", response_class=HTMLResponse)
def api_preview() -> HTMLResponse:
    return HTMLResponse(service.render_preview())


@app.post("/api/article/{index}/regenerate")
def api_article_regenerate(index: int) -> JSONResponse:
    return JSONResponse(service.regenerate_article_auto(index))


@app.post("/api/article/{index}/replace")
def api_article_replace(index: int, body: TopicBody) -> JSONResponse:
    return JSONResponse(service.replace_article_by_topic(index, body.topic))


@app.post("/api/joke/regenerate")
def api_joke_regenerate() -> JSONResponse:
    return JSONResponse(service.regenerate_joke())


@app.post("/api/concept/regenerate")
def api_concept_regenerate() -> JSONResponse:
    return JSONResponse(service.regenerate_concept())


@app.post("/api/concept/custom")
def api_concept_custom(body: TopicBody) -> JSONResponse:
    return JSONResponse(service.set_custom_concept(body.topic))


@app.post("/api/send")
def api_send() -> JSONResponse:
    return JSONResponse(service.send_now())


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
