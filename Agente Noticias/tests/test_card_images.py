"""Tests for the newsletter card image pipeline (no network)."""
from __future__ import annotations

import base64
import io
from typing import get_args

import pytest
from PIL import Image

from agente_noticias import card_images
from agente_noticias.card_images import (
    BADGE_HEIGHT,
    CARD_SIZE,
    build_card_image,
    card_filename,
    compose_card,
    decode_image_response,
    parse_og_image,
)
from agente_noticias.config import COMPANY_LOGOS_DIR
from agente_noticias.logos import COMPANY_DISPLAY_NAMES
from agente_noticias.nodes import persist_history
from agente_noticias.nodes import card_images as card_images_node_mod
from agente_noticias.nodes.card_images import attach_card_image, project_relative
from agente_noticias.schemas import (
    Article,
    ArticleEvaluation,
    CompanyKey,
    EvaluatedArticle,
)

W, H = CARD_SIZE


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any real HTTP attempt fails the test."""

    def _blocked(*args, **kwargs):
        raise AssertionError("network access attempted in tests")

    monkeypatch.setattr(card_images.httpx, "post", _blocked)
    monkeypatch.setattr(card_images.httpx, "Client", _blocked)


def _solid(color, size=(800, 600)) -> Image.Image:
    return Image.new("RGB", size, color)


def _white_ratio(img: Image.Image, box) -> float:
    region = img.crop(box)
    px = [region.getpixel((x, y)) for y in range(region.height) for x in range(region.width)]
    white = sum(1 for r, g, b, a in px if a == 255 and min(r, g, b) > 240)
    return white / len(px)


# Badge region away from the rounded bottom-left corner.
BADGE_BOX = (20, H - BADGE_HEIGHT + 4, 110, H - 4)


def test_compose_card_with_company_has_size_alpha_and_white_badge():
    card = compose_card(_solid((0, 0, 0)), "openai")

    assert card.size == (528, 370)
    assert card.mode == "RGBA"
    for corner in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)):
        assert card.getpixel(corner)[3] == 0
    assert card.getpixel((W // 2, H // 2))[3] == 255
    assert _white_ratio(card, BADGE_BOX) > 0.5


def test_compose_card_without_company_has_no_badge():
    card = compose_card(_solid((0, 0, 0)), None)

    assert card.size == (528, 370)
    assert _white_ratio(card, BADGE_BOX) == 0


def test_compose_card_missing_logo_still_draws_name_badge(tmp_path):
    card = compose_card(_solid((0, 0, 0)), "openai", logos_dir=tmp_path)

    assert _white_ratio(card, BADGE_BOX) > 0.5


def test_every_company_key_has_display_name_and_logo():
    keys = set(get_args(CompanyKey))
    assert keys == set(COMPANY_DISPLAY_NAMES)
    for key in keys:
        logo = Image.open(COMPANY_LOGOS_DIR / f"{key}.png")
        assert logo.mode == "RGBA"
        assert logo.height == 128


def test_parse_og_image_resolves_relative_and_prefers_og():
    html = """<html><head>
      <meta name="twitter:image" content="https://cdn.example.com/tw.jpg">
      <meta property="og:image" content="/img/hero.png?a=1&amp;b=2">
    </head><body></body></html>"""

    url = parse_og_image(html, "https://news.example.com/2026/10/story")

    assert url == "https://news.example.com/img/hero.png?a=1&b=2"


def test_parse_og_image_falls_back_to_twitter_and_none():
    tw = '<meta name="twitter:image" content="https://cdn.example.com/tw.jpg">'
    assert parse_og_image(tw, "https://x.com/a") == "https://cdn.example.com/tw.jpg"
    assert parse_og_image("<html><head><title>x</title></head></html>", "https://x.com") is None


def test_decode_image_response_reads_b64_json_and_data_url():
    buf = io.BytesIO()
    _solid((255, 90, 10), (300, 200)).save(buf, "PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    img = decode_image_response({"data": [{"b64_json": b64, "media_type": "image/png"}]})
    assert img.size == (300, 200)
    img = decode_image_response({"data": [{"url": f"data:image/png;base64,{b64}"}]})
    assert img.size == (300, 200)
    with pytest.raises(card_images.ImageGenerationError):
        decode_image_response({"data": []})


def _fail(*args, **kwargs):
    raise card_images.ImageGenerationError("HTTP 500: boom")


def test_fallback_uses_placeholder_when_everything_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(card_images, "generate_illustration", _fail)
    monkeypatch.setattr(card_images, "download_image", _fail)
    monkeypatch.setattr(card_images, "fetch_og_image", _fail)

    out = build_card_image(
        out_path=tmp_path / "x" / "card.png",
        title="OpenAI lanza algo",
        company="google",
        image_url="https://cdn.example.com/a.jpg",
        article_url="https://news.example.com/a",
        generate=True,
    )

    assert out.is_file()
    img = Image.open(out)  # palette PNG (see save_card_png)
    assert img.size == (528, 370) and img.convert("RGBA").getpixel((0, 0))[3] == 0


def test_fallback_uses_og_image_when_ai_fails(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(card_images, "generate_illustration", _fail)

    def fake_og(url):
        calls.append(url)
        return _solid((255, 0, 0))

    monkeypatch.setattr(card_images, "fetch_og_image", fake_og)

    out = build_card_image(
        out_path=tmp_path / "card.png",
        title="Noticia",
        company=None,
        article_url="https://news.example.com/a",
        generate=True,
    )

    assert calls == ["https://news.example.com/a"]
    r, g, b, a = Image.open(out).convert("RGBA").getpixel((W // 2, H // 2))
    assert (r, g, b) == (255, 0, 0) and a >= 250  # palette quantization may round alpha


def test_images_disabled_skips_ai(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWS_IMAGES_ENABLED", "false")
    monkeypatch.setattr(card_images, "generate_illustration", lambda *a, **k: pytest.fail("AI called"))

    out = build_card_image(out_path=tmp_path / "card.png", title="Sin IA")

    assert out.is_file()


def _evaluated(**article_extra) -> EvaluatedArticle:
    return EvaluatedArticle(
        article=Article(title="OpenAI lanza un agente", url="https://news.example.com/a", **article_extra),
        evaluation=ArticleEvaluation(
            reasoning="r",
            relevance_score=8,
            category="IA agentica",
            label_es="Agentes",
            title_es="OpenAI lanza un agente",
            summary_es="Resumen.",
            company="openai",
        ),
    )


def test_attach_card_image_sets_path_and_persist_passes_relative_path(tmp_path, monkeypatch):
    monkeypatch.setattr(card_images, "generate_illustration", _fail)
    monkeypatch.setattr(card_images, "fetch_og_image", lambda url: None)

    item = attach_card_image(_evaluated(), out_dir=tmp_path)
    assert item.card_image_path and (tmp_path / card_filename(item.article.title, item.article.url)).is_file()

    captured = {}
    monkeypatch.setattr(persist_history, "save_briefing", lambda **kw: captured.update(kw) or "id-1")
    monkeypatch.setattr(persist_history, "project_relative", lambda p: f"rel:{p}")
    persist_history.persist_history_node(
        {"send_ok": True, "send_result": "ok", "selected_articles": [item], "subject": "s"}
    )

    saved = captured["articles"][0]
    assert saved["company"] == "openai"
    assert saved["image_path"] == f"rel:{item.card_image_path}"


def test_project_relative_and_card_filename():
    from agente_noticias.config import PROJECT_DIR

    assert project_relative(str(PROJECT_DIR / "data" / "images" / "a.png")) == "data/images/a.png"
    assert project_relative(None) is None
    name = card_filename("¡OpenAI lanza un agente que trabaja mientras duermes!", "https://x.com/a")
    assert name.startswith("openai-lanza-un-agente-que-trabaja-mientras-duermes-")
    assert name.endswith(".png")


def test_persist_history_skips_when_send_not_ok(monkeypatch):
    monkeypatch.setattr(persist_history, "save_briefing", lambda **kw: pytest.fail("saved"))
    item = _evaluated()
    # The old heuristic matched "enviado" in the text; only the explicit flag counts now.
    for state in (
        {"send_ok": False, "send_result": "Correo enviado? no", "selected_articles": [item]},
        {"send_result": "Correo enviado a x", "selected_articles": [item]},
    ):
        assert persist_history.persist_history_node(state) == {}


def test_card_images_node_isolates_a_failing_card(tmp_path, monkeypatch, capsys):
    good, bad = _evaluated(), _evaluated()
    bad = bad.model_copy(update={"article": bad.article.model_copy(update={"url": "https://bad.example.com"})})

    def fake_attach(item, out_dir=None):
        if item.article.url == "https://bad.example.com":
            raise RuntimeError("unexpected")
        return item.model_copy(update={"card_image_path": str(tmp_path / "ok.png")})

    monkeypatch.setattr(card_images_node_mod, "attach_card_image", fake_attach)
    result = card_images_node_mod.card_images_node({"selected_articles": [good, bad]})

    out = result["selected_articles"]
    assert [it.article.url for it in out] == [good.article.url, "https://bad.example.com"]
    assert out[0].card_image_path and out[1].card_image_path is None
    assert "card task failed for https://bad.example.com" in capsys.readouterr().err


def test_attach_card_image_never_raises(monkeypatch):
    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(card_images_node_mod, "build_card_image", boom)
    item = attach_card_image(_evaluated())
    assert item.card_image_path is None


class _FakeResp:
    def __init__(self, status=200, json_data=None, text=""):
        self.status_code, self._json, self.text = status, json_data, text

    def json(self):
        if self._json is None:
            raise ValueError("not json")
        return self._json


@pytest.mark.parametrize(
    "resp",
    [
        _FakeResp(text="<html>gateway</html>"),
        _FakeResp(json_data=["not", "a", "dict"]),
        _FakeResp(json_data={"data": [{"b64_json": "%%%not-base64%%%"}]}),
        _FakeResp(json_data={"data": [{"b64_json": base64.b64encode(b"not an image").decode()}]}),
    ],
)
def test_generate_illustration_bad_200_raises_generation_error(monkeypatch, resp):
    monkeypatch.setattr(card_images.httpx, "post", lambda *a, **k: resp)
    with pytest.raises(card_images.ImageGenerationError):
        card_images.generate_illustration("robot", api_key="k", model="m", quality="low")


def test_open_image_rejects_oversized_pixels(monkeypatch):
    buf = io.BytesIO()
    _solid((1, 2, 3), (400, 300)).save(buf, "PNG")
    monkeypatch.setattr(card_images, "MAX_SOURCE_PIXELS", 100_000)
    with pytest.raises(ValueError, match="too large"):
        card_images._open_image(buf.getvalue())


def test_save_card_png_fits_outlook_web_budget_and_keeps_alpha(tmp_path):
    card = card_images.compose_card(card_images.placeholder_image(seed="owa"), "openai")
    out = tmp_path / "card.png"
    size = card_images.save_card_png(card, out)
    assert size == out.stat().st_size <= card_images.MAX_CARD_BYTES
    saved = Image.open(out).convert("RGBA")
    assert saved.size == card_images.CARD_SIZE
    assert saved.getpixel((0, 0))[3] == 0  # rounded corner stays transparent
