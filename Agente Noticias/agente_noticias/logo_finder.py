"""Logo finder: learns the logo of a company that has none in the library.

A small LangChain tool-calling agent (`langchain.agents.create_agent`) whose only job
is to pick the right Wikidata entity for a company name. Everything else is
deterministic code: the Wikidata search, reading the logo statements (P8972 "small
logo or icon" first, then P154 "logo image"), downloading a PNG render from Wikimedia
Commons, validating and normalizing it, and recording it in the registry.

To save LLM calls, `ensure_logo` runs the first `search_company` itself and hands the
candidates to the agent, and `save_company_logo` returns directly (no final LLM turn):
a typical lookup costs ONE chat call.

`ensure_logo` never raises: any failure logs a warning and returns None (the card
then shows a name-only badge). Misses are cached for the run and persisted as a
"not_found" marker for NOT_FOUND_TTL so the agent is not retried every week.
"""
from __future__ import annotations

import io
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import httpx
from PIL import Image, ImageChops

from agente_noticias._concurrency import submit_with_context
from agente_noticias.logos import (
    company_slug,
    display_name,
    learned_logos_dir,
    load_registry,
    logo_path,
    update_registry,
)

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_FILE_PATH = "https://commons.wikimedia.org/wiki/Special:FilePath/{file}"
COMMONS_FILE_PAGE = "https://commons.wikimedia.org/wiki/File:{file}"
# Wikimedia API etiquette: identify the tool and a contact URL.
HTTP_HEADERS = {
    "User-Agent": (
        "AgenteNoticiasWIN/1.0 (https://win.pe; weekly AI newsletter logo lookup) "
        f"python-httpx/{httpx.__version__}"
    ),
    "Accept": "application/json, image/png, image/*;q=0.8",
}
HTTP_TIMEOUT = 10.0
AGENT_TIMEOUT = 60.0
AGENT_RECURSION_LIMIT = 10
SEARCH_LIMIT = 5
SEARCH_LANGUAGES = ("en", "es")
# P8972 = small logo or icon (preferred: the name is drawn next to it); P154 = logo image.
LOGO_PROPERTIES = ("P8972", "P154")
RENDER_WIDTH = 512
MAX_LOGO_BYTES = 5_000_000
MAX_LOGO_PIXELS = 25_000_000
NORMALIZED_HEIGHT = 128
MAX_NORMALIZED_WIDTH = NORMALIZED_HEIGHT * 8
NOT_FOUND_TTL = timedelta(days=30)

AGENT_SYSTEM_PROMPT = """You find the official logo of a company for a news card badge.

You get a company name and Wikidata candidates (from `search_company`): id, label,
description and the logo files each one has (`icon` = P8972, `logo` = P154).

Rules:
- Choose the entity that IS the company or organization. A product or service is fine
  only when that product IS the brand (e.g. a well-known app named like the company).
  Never choose a person, place, event, creative work, file format or a regional
  subsidiary/division unless that is exactly what was asked.
- The chosen entity must have a logo (`icon` or `logo` not null).
- If no candidate fits, you may call `search_company` ONCE with a better query (for
  example the full official name).
- Then call `save_company_logo` exactly once with the chosen id.
- If no entity is the company or none has a logo, do not save anything: reply
  "NOT_FOUND: <short reason>".
"""

_run_misses: set[str] = set()
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _warn(message: str) -> None:
    print(f"[logo_finder] WARNING: {message}", file=sys.stderr)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# HTTP + Wikidata (deterministic)
# --------------------------------------------------------------------------- #
def _http_get(url: str, params: dict | None = None) -> httpx.Response:
    resp = httpx.get(
        url, params=params, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT, follow_redirects=True
    )
    resp.raise_for_status()
    return resp


def _wikidata(params: dict) -> dict:
    data = _http_get(WIKIDATA_API, {**params, "format": "json"}).json()
    if not isinstance(data, dict) or "error" in data:
        raise ValueError(f"Wikidata error: {str(data)[:200]}")
    return data


def _best_file(claims: dict, prop: str) -> str | None:
    """Commons file name of the best statement: preferred rank, then without end date."""
    statements = [
        s
        for s in claims.get(prop, [])
        if s.get("rank") != "deprecated" and s.get("mainsnak", {}).get("snaktype") == "value"
    ]
    if not statements:
        return None
    best = max(
        statements,
        key=lambda s: (s.get("rank") == "preferred", "P582" not in (s.get("qualifiers") or {})),
    )
    value = best["mainsnak"].get("datavalue", {}).get("value")
    return value if isinstance(value, str) and value.strip() else None


def _entity_claims(qids: list[str]) -> dict[str, dict]:
    if not qids:
        return {}
    data = _wikidata({"action": "wbgetentities", "ids": "|".join(qids), "props": "claims"})
    return {qid: (ent.get("claims") or {}) for qid, ent in (data.get("entities") or {}).items()}


def search_company(name: str) -> list[dict]:
    """Top Wikidata items for `name` with their logo files (None when missing)."""
    hits: list[dict] = []
    for lang in SEARCH_LANGUAGES:
        data = _wikidata(
            {
                "action": "wbsearchentities",
                "search": name,
                "language": lang,
                "uselang": lang,
                "type": "item",
                "limit": SEARCH_LIMIT,
            }
        )
        hits = data.get("search") or []
        if hits:
            break
    claims = _entity_claims([h["id"] for h in hits if h.get("id")])
    return [
        {
            "qid": h["id"],
            "label": h.get("label", ""),
            "description": h.get("description", ""),
            "icon": _best_file(claims.get(h["id"], {}), "P8972"),
            "logo": _best_file(claims.get(h["id"], {}), "P154"),
        }
        for h in hits
        if h.get("id")
    ]


# --------------------------------------------------------------------------- #
# Logo download + normalization (deterministic)
# --------------------------------------------------------------------------- #
def normalize_logo(data: bytes) -> Image.Image:
    """RGBA logo trimmed to its visible (non-transparent, non-white) area, 128 px tall."""
    img = Image.open(io.BytesIO(data))
    if img.width * img.height > MAX_LOGO_PIXELS:
        raise ValueError(f"logo too large ({img.width}x{img.height})")
    img = img.convert("RGBA")
    r, g, b, a = img.split()
    opaque = a.point(lambda v: 255 if v > 16 else 0)
    darkest = ImageChops.darker(ImageChops.darker(r, g), b)
    non_white = darkest.point(lambda v: 255 if v < 240 else 0)
    bbox = ImageChops.multiply(opaque, non_white).getbbox()
    if bbox is None:
        raise ValueError("logo is blank or white-only (invisible on the white badge)")
    img = img.crop(bbox)
    if img.width < 8 or img.height < 8:
        raise ValueError(f"logo too small after trimming ({img.width}x{img.height})")
    width = round(img.width * NORMALIZED_HEIGHT / img.height)
    height = NORMALIZED_HEIGHT
    if width > MAX_NORMALIZED_WIDTH:
        width, height = MAX_NORMALIZED_WIDTH, round(img.height * MAX_NORMALIZED_WIDTH / img.width)
    return img.resize((width, max(1, height)), Image.LANCZOS)


def _download_render(file_name: str) -> tuple[Image.Image, str]:
    """PNG render of a Commons file (SVGs are rasterized by Commons) + its URL."""
    url = COMMONS_FILE_PATH.format(file=quote(file_name.replace(" ", "_")))
    resp = _http_get(url, {"width": RENDER_WIDTH})
    ctype = resp.headers.get("content-type", "")
    if not ctype.startswith("image/"):
        raise ValueError(f"not an image ({ctype or 'no content-type'})")
    if len(resp.content) > MAX_LOGO_BYTES:
        raise ValueError(f"logo larger than {MAX_LOGO_BYTES} bytes")
    return normalize_logo(resp.content), f"{url}?width={RENDER_WIDTH}"


def _save_png(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
    img.save(tmp, "PNG", optimize=True)
    os.replace(tmp, path)


def save_company_logo(qid: str, slug: str, name: str) -> str:
    """Downloads the logo of Wikidata item `qid` and stores it as `<slug>.png` + registry."""
    qid = (qid or "").strip().upper()
    if not qid.startswith("Q") or not qid[1:].isdigit():
        return f"FAILED: '{qid}' is not a Wikidata item id (Q123)."
    claims = _entity_claims([qid]).get(qid, {})
    errors: list[str] = []
    for prop in LOGO_PROPERTIES:
        file_name = _best_file(claims, prop)
        if not file_name:
            continue
        try:
            img, source_url = _download_render(file_name)
        except Exception as exc:  # noqa: BLE001 - try the next property
            errors.append(f"{prop} {file_name}: {exc}")
            continue
        path = learned_logos_dir() / f"{slug}.png"
        _save_png(img, path)
        update_registry(
            slug,
            {
                "status": "found",
                "display_name": name,
                "qid": qid,
                "property": prop,
                "file": file_name,
                "source_url": source_url,
                "file_page": COMMONS_FILE_PAGE.format(file=quote(file_name.replace(" ", "_"))),
                "size": list(img.size),
                "saved_at": _now().isoformat(timespec="seconds"),
            },
        )
        return f"SAVED: logo of {name} from {qid} {prop} '{file_name}' ({img.width}x{img.height})."
    detail = "; ".join(errors) if errors else "it has no P8972/P154 logo statement"
    return f"FAILED: {qid}: {detail}."


# --------------------------------------------------------------------------- #
# Agent
# --------------------------------------------------------------------------- #
def build_logo_agent(name: str, slug: str, model=None):
    """Tool-calling agent bound to one company (the slug/name never come from the LLM)."""
    from langchain.agents import create_agent
    from langchain_core.tools import tool

    from agente_noticias.config import get_eval_model
    from agente_noticias.llm import get_chat_model

    state = {"saved": False}

    @tool("search_company")
    def search_company_tool(query: str) -> str:
        """Search Wikidata for a company/organization; returns candidates with their logo files."""
        return json.dumps(search_company(query), ensure_ascii=False)

    @tool("save_company_logo", return_direct=True)
    def save_company_logo_tool(qid: str) -> str:
        """Download and store the logo of the chosen Wikidata item (e.g. 'Q483551')."""
        if state["saved"]:
            return "ALREADY SAVED: only one logo per company."
        result = save_company_logo(qid, slug, name)
        state["saved"] = result.startswith("SAVED")
        return result

    return create_agent(
        model or get_chat_model(get_eval_model()),
        tools=[search_company_tool, save_company_logo_tool],
        system_prompt=AGENT_SYSTEM_PROMPT,
        name="logo_finder",
    )


def _run_agent(name: str, slug: str) -> None:
    """Initial search (no LLM), then the agent picks and saves (usually one LLM call)."""
    candidates = search_company(name)
    if not candidates:
        print(f"[logo_finder] '{name}': no Wikidata candidates")
        return
    agent = build_logo_agent(name, slug)
    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": (
                        f"Company: {name}\n"
                        "Wikidata candidates (search_company result):\n"
                        f"{json.dumps(candidates, ensure_ascii=False, indent=1)}"
                    ),
                }
            ]
        },
        config={"recursion_limit": AGENT_RECURSION_LIMIT},
    )
    last = result["messages"][-1].content if result.get("messages") else ""
    print(f"[logo_finder] '{name}': {str(last)[:200]}")


def _run_with_timeout(name: str, slug: str, timeout: float) -> bool:
    """Runs the agent; True if it finished (found or not), False on error/timeout."""
    pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="logo_finder")
    future = submit_with_context(pool, _run_agent, name, slug)
    try:
        future.result(timeout=timeout)
        return True
    except FuturesTimeout:
        _warn(f"'{name}': agent timed out after {timeout:.0f}s")
    except Exception as exc:  # noqa: BLE001
        _warn(f"'{name}': agent failed: {type(exc).__name__}: {exc}")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
    return False


def _recently_not_found(slug: str) -> bool:
    entry = load_registry().get(slug) or {}
    if entry.get("status") != "not_found":
        return False
    try:
        checked = datetime.fromisoformat(entry["checked_at"])
    except (KeyError, TypeError, ValueError):
        return False
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=timezone.utc)
    return _now() - checked < NOT_FOUND_TTL


def _lock_for(slug: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(slug, threading.Lock())


def _ensure_logo(company: str | None, timeout: float) -> Path | None:
    slug = company_slug(company)
    if slug is None:
        return None
    path = logo_path(company)
    if path is not None:
        return path
    if slug in _run_misses or _recently_not_found(slug):
        return None
    with _lock_for(slug):  # cards run in parallel: one lookup per company
        path = logo_path(company)
        if path is not None or slug in _run_misses:
            return path
        name = display_name(company)
        print(f"[logo_finder] '{name}': no logo stored, asking the agent")
        completed = _run_with_timeout(name, slug, timeout)
        path = logo_path(company)
        if path is not None:
            return path
        _run_misses.add(slug)
        if completed:  # a genuine miss, not a transient error: don't retry for a while
            update_registry(
                slug,
                {
                    "status": "not_found",
                    "display_name": name,
                    "checked_at": _now().isoformat(timespec="seconds"),
                },
            )
        return None


def ensure_logo(company: str | None, *, timeout: float = AGENT_TIMEOUT) -> Path | None:
    """Logo path of `company` (built-in, learned, or found now by the agent); never raises."""
    try:
        return _ensure_logo(company, timeout)
    except Exception as exc:  # noqa: BLE001 - a logo never blocks the newsletter
        _warn(f"'{company}': {type(exc).__name__}: {exc}")
        return None
