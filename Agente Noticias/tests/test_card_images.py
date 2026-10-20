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
    img = Image.open(out)
    assert img.size == (528, 370) and img.mode == "RGBA"


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
    r, g, b, a = Image.open(out).getpixel((W // 2, H // 2))
    assert (r, g, b, a) == (255, 0, 0, 255)


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
            summary_es="Resumen.",
            en_simple="Simple.",
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
        {"send_result": "Enviado OK", "selected_articles": [item], "subject": "s"}
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
