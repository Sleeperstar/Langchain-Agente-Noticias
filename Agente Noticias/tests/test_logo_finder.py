"""Logo finder agent (no network, no real LLM): HTTP and the chat model are faked."""
from __future__ import annotations

import io
import json
import threading
from datetime import timedelta

import httpx
import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from PIL import Image

from agente_noticias import llm, logo_finder, logos
from agente_noticias.config import COMPANY_LOGOS_DIR


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Learned logos go to tmp; no real HTTP; fresh run-level cache."""
    monkeypatch.setattr(logos, "LEARNED_LOGOS_DIR", tmp_path)
    monkeypatch.setattr(logo_finder, "_run_misses", set())
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")

    def _blocked(*args, **kwargs):
        raise AssertionError("network access attempted in tests")

    monkeypatch.setattr(logo_finder.httpx, "get", _blocked)
    return tmp_path


def _png(size=(400, 400), color=(20, 120, 220, 255), margin=50) -> bytes:
    """Colored square on a white margin (the margin must be trimmed)."""
    img = Image.new("RGBA", size, (255, 255, 255, 255))
    img.paste(Image.new("RGBA", (size[0] - 2 * margin, size[1] - 2 * margin), color), (margin, margin))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _statement(file_name, rank="normal", ended=False):
    st = {"rank": rank, "mainsnak": {"snaktype": "value", "datavalue": {"value": file_name}}}
    if ended:
        st["qualifiers"] = {"P582": [{}]}
    return st


class FakeWikimedia:
    """Fake `_http_get`: one company 'Acme' (Q1) with an icon and a logo."""

    def __init__(self, png: bytes | None = None):
        self.png = png or _png()
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url, params=None):
        params = params or {}
        self.calls.append((url, params))
        req = httpx.Request("GET", url)
        if url == logo_finder.WIKIDATA_API and params["action"] == "wbsearchentities":
            hits = [{"id": "Q1", "label": "Acme", "description": "company"}]
            hits.append({"id": "Q2", "label": "Acme", "description": "song"})
            return httpx.Response(200, json={"search": hits}, request=req)
        if url == logo_finder.WIKIDATA_API and params["action"] == "wbgetentities":
            entities = {
                "Q1": {"claims": {"P8972": [_statement("Acme icon.svg")], "P154": [_statement("Acme logo.svg")]}},
                "Q2": {"claims": {}},
            }
            wanted = params["ids"].split("|")
            return httpx.Response(200, json={"entities": {q: entities[q] for q in wanted}}, request=req)
        if url.startswith("https://commons.wikimedia.org/wiki/Special:FilePath/"):
            return httpx.Response(200, content=self.png, headers={"content-type": "image/png"}, request=req)
        raise AssertionError(f"unexpected URL {url}")


class FakeToolModel(GenericFakeChatModel):
    """Fake chat model usable by create_agent (bind_tools is a no-op)."""

    def bind_tools(self, tools, **kwargs):
        return self


def _fake_model(monkeypatch, *messages):
    """The agent's model replies with `messages` in order; returns a call counter."""
    calls = {"n": 0}

    def script():
        for message in messages:
            calls["n"] += 1
            yield message

    model = FakeToolModel(messages=script())
    monkeypatch.setattr(llm, "get_chat_model", lambda *a, **k: model)
    return calls


def _save_call(qid="Q1"):
    return AIMessage(content="", tool_calls=[{"name": "save_company_logo", "args": {"qid": qid}, "id": "call_1"}])


def test_builtin_logo_is_returned_without_agent(monkeypatch):
    monkeypatch.setattr(logo_finder, "_run_agent", lambda *a: pytest.fail("agent called"))
    assert logo_finder.ensure_logo("OpenAI") == COMPANY_LOGOS_DIR / "openai.png"
    assert logo_finder.ensure_logo("Google DeepMind") == COMPANY_LOGOS_DIR / "google.png"


def test_learned_logo_is_returned_without_agent(isolated, monkeypatch):
    (isolated / "acme.png").write_bytes(_png())
    monkeypatch.setattr(logo_finder, "_run_agent", lambda *a: pytest.fail("agent called"))
    assert logo_finder.ensure_logo("Acme") == isolated / "acme.png"


def test_blank_company_returns_none():
    assert logo_finder.ensure_logo(None) is None
    assert logo_finder.ensure_logo("  ") is None


def test_agent_saves_logo_and_registry_entry(isolated, monkeypatch):
    http = FakeWikimedia()
    monkeypatch.setattr(logo_finder, "_http_get", http)
    calls = _fake_model(monkeypatch, _save_call("Q1"))

    path = logo_finder.ensure_logo("Acme Inc.")

    assert path == isolated / "acme.png" and path.is_file()
    assert calls["n"] == 1  # search is pre-run, save returns directly: one LLM call
    img = Image.open(path)
    assert img.mode == "RGBA" and img.height == logo_finder.NORMALIZED_HEIGHT
    assert img.width == img.height  # white margins trimmed -> square
    entry = json.loads((isolated / "registry.json").read_text(encoding="utf-8"))["acme"]
    assert entry["status"] == "found"
    assert entry["display_name"] == "Acme Inc."
    assert (entry["qid"], entry["property"], entry["file"]) == ("Q1", "P8972", "Acme icon.svg")
    assert entry["file_page"] == "https://commons.wikimedia.org/wiki/File:Acme_icon.svg"
    assert entry["source_url"].startswith("https://commons.wikimedia.org/wiki/Special:FilePath/Acme_icon.svg")
    assert entry["saved_at"]
    # A second lookup hits the cache.
    monkeypatch.setattr(logo_finder, "_run_agent", lambda *a: pytest.fail("agent called"))
    assert logo_finder.ensure_logo("Acme") == path


def test_agent_not_found_persists_marker_and_prevents_retry(isolated, monkeypatch):
    monkeypatch.setattr(logo_finder, "_http_get", FakeWikimedia())
    _fake_model(monkeypatch, AIMessage(content="NOT_FOUND: no candidate is the company"))

    assert logo_finder.ensure_logo("Acme") is None
    entry = json.loads((isolated / "registry.json").read_text(encoding="utf-8"))["acme"]
    assert entry["status"] == "not_found" and entry["checked_at"]

    # New run (empty in-memory cache): the persisted marker still prevents a retry...
    monkeypatch.setattr(logo_finder, "_run_misses", set())
    monkeypatch.setattr(logo_finder, "_run_agent", lambda *a: pytest.fail("agent called"))
    assert logo_finder.ensure_logo("Acme") is None

    # ...until it expires.
    ran = []
    monkeypatch.setattr(logo_finder, "_now", lambda: logo_finder.datetime.now(logo_finder.timezone.utc) + timedelta(days=31))
    monkeypatch.setattr(logo_finder, "_run_agent", lambda name, slug: ran.append(slug))
    assert logo_finder.ensure_logo("Acme") is None
    assert ran == ["acme"]


def test_agent_error_returns_none_without_persisting_marker(isolated, monkeypatch):
    def boom(name, slug):
        raise RuntimeError("OpenRouter 500")

    monkeypatch.setattr(logo_finder, "_run_agent", boom)
    assert logo_finder.ensure_logo("Acme") is None
    assert not (isolated / "registry.json").exists()  # transient: retried next run
    # ...but not again in this run.
    monkeypatch.setattr(logo_finder, "_run_agent", lambda *a: pytest.fail("agent called"))
    assert logo_finder.ensure_logo("Acme") is None


def test_any_unexpected_exception_returns_none(monkeypatch):
    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(logo_finder, "logo_path", boom)
    assert logo_finder.ensure_logo("Acme") is None


def test_agent_timeout_returns_none(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(logo_finder, "_run_agent", lambda name, slug: release.wait(5))
    try:
        assert logo_finder.ensure_logo("Acme", timeout=0.05) is None
    finally:
        release.set()


def test_save_falls_back_to_p154_and_rejects_white_only_logo(isolated, monkeypatch):
    white = _png(color=(255, 255, 255, 255))
    http = FakeWikimedia(png=white)
    monkeypatch.setattr(logo_finder, "_http_get", http)

    result = logo_finder.save_company_logo("Q1", "acme", "Acme")

    assert result.startswith("FAILED") and "white-only" in result
    assert [p.get("width") for u, p in http.calls if "FilePath" in u] == [512, 512]  # icon, then logo
    assert not (isolated / "acme.png").exists()
    assert logo_finder.save_company_logo("bad id", "acme", "Acme").startswith("FAILED")


def test_best_file_prefers_preferred_rank_and_current_statements():
    claims = {
        "P154": [
            _statement("old.svg", ended=True),
            _statement("current.svg"),
            _statement("deprecated.svg", rank="deprecated"),
        ]
    }
    assert logo_finder._best_file(claims, "P154") == "current.svg"
    claims["P154"].append(_statement("preferred.svg", rank="preferred"))
    assert logo_finder._best_file(claims, "P154") == "preferred.svg"
    assert logo_finder._best_file(claims, "P8972") is None


def test_search_company_reports_logo_files(monkeypatch):
    monkeypatch.setattr(logo_finder, "_http_get", FakeWikimedia())
    out = logo_finder.search_company("Acme")
    assert out[0] == {"qid": "Q1", "label": "Acme", "description": "company", "icon": "Acme icon.svg", "logo": "Acme logo.svg"}
    assert out[1]["icon"] is None and out[1]["logo"] is None
