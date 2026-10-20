"""Tests for the newsletter HTML template and the inline-image (CID) plumbing."""
from __future__ import annotations

from datetime import date

import pytest
from PIL import Image

from agente_noticias import email_template
from agente_noticias.email_template import (
    card_label,
    display_headline,
    inline_images,
    render_email,
)
from agente_noticias.nodes.outlook_sender import (
    PR_ATTACH_CONTENT_ID,
    PR_ATTACH_HIDDEN,
    attach_inline_images,
)
from agente_noticias.schemas import Article, ArticleEvaluation, Briefing, EvaluatedArticle

COMPANIES = ["openai", "google", "anthropic"]


def _png(path) -> str:
    Image.new("RGBA", (528, 370), (255, 90, 10, 255)).save(path, "PNG")
    return str(path)


@pytest.fixture()
def logo(tmp_path, monkeypatch):
    path = tmp_path / "win_logo.png"
    _png(path)
    monkeypatch.setattr(email_template, "LOGO_PATH", path)
    return path


def _item(n: int, image: str | None, company: str | None = "openai", **ev) -> EvaluatedArticle:
    fields = {
        "reasoning": "r",
        "relevance_score": 8,
        "category": "Nuevos modelos",
        "company": company,
        "label_es": "Lanzamiento",
        "title_es": f"Titulo tarjeta {n}",
        "summary_es": f"Resumen corto numero {n}. Y un gancho final.",
        **ev,
    }
    return EvaluatedArticle(
        article=Article(title=f"English title {n}", url=f"https://example.com/n{n}"),
        evaluation=ArticleEvaluation(**fields),
        card_image_path=image,
    )


def _items(tmp_path, n: int = 3) -> list[EvaluatedArticle]:
    return [
        _item(i, _png(tmp_path / f"card{i}.png"), company=COMPANIES[i % len(COMPANIES)])
        for i in range(n)
    ]


BRIEFING = Briefing(
    headline="La IA se pone a trabajar - 2026-10-20",
    concepto_titulo="Que es un token?",
    concepto_explicacion="Es un pedacito de texto. Asi lee la IA.",
    chiste="Por que la IA fue al gimnasio? Para entrenar sus modelos.",
)


def _render(items, images):
    return render_email(BRIEFING, items, "gpt-x", "proj", "run-1", images=images, today=date(2026, 10, 20))


def test_send_mode_renders_every_card_with_cid_refs(tmp_path, logo):
    items = _items(tmp_path, 3)
    html = _render(items, "cid")

    assert html.count('class="card-txt"') == 3
    for i in range(1, 4):
        assert f'src="cid:card{i}"' in html
        assert f"Titulo tarjeta {i - 1}" in html
    assert 'src="cid:winlogo"' in html
    assert "data:image" not in html
    assert "Leer más" in html and "Esta semana en IA" in html
    assert "20 de octubre de 2026" in html

    cids = [cid for _, cid in inline_images(items)]
    assert cids == ["winlogo", "card1", "card2", "card3"]


def test_preview_mode_uses_data_uris(tmp_path, logo):
    html = _render(_items(tmp_path, 3), "data")

    assert html.count("data:image/png;base64,") == 4  # logo + 3 cards
    assert "cid:" not in html


def test_card_without_image_renders_text_only(tmp_path, logo):
    items = _items(tmp_path, 2)
    items.append(_item(9, None))
    items.append(_item(10, str(tmp_path / "missing.png")))
    html = _render(items, "cid")

    assert html.count('class="card-txt"') == 4
    assert html.count('class="card-img"') == 2
    assert "Titulo tarjeta 9" in html and "Titulo tarjeta 10" in html
    assert "cid:card3" not in html and "cid:card4" not in html
    assert [cid for _, cid in inline_images(items)] == ["winlogo", "card1", "card2"]


def test_no_tldr_and_concept_joke_kept(tmp_path, logo):
    for mode in ("cid", "data"):
        html = _render(_items(tmp_path, 1), mode)
        lowered = html.lower()
        assert "tl;dr" not in lowered and "tldr" not in lowered
        assert "lectura de 30 segundos" not in lowered
        assert "Concepto del día" in html and "Que es un token?" in html
        assert "Para cerrar con humor winner" in html
        assert "Relevancia" not in html and "En simple" not in html


def test_headline_date_is_shown_once(tmp_path, logo):
    html = _render(_items(tmp_path, 1), "data")
    assert "La IA se pone a trabajar" in html
    assert "2026-10-20" not in html
    assert display_headline("Hola - 2026-10-20") == "Hola"
    assert display_headline("Sin fecha") == "Sin fecha"


def test_card_label_and_fallbacks():
    assert card_label(_item(1, None, company="openai")) == "LANZAMIENTO · OPENAI"
    assert card_label(_item(1, None, company=None)) == "LANZAMIENTO"
    fallback = _item(1, None, company="google", label_es=" ", category="Herramientas y productos")
    assert card_label(fallback) == "HERRAMIENTAS · GOOGLE"


def test_missing_title_es_falls_back_and_text_is_escaped(tmp_path, logo):
    item = _item(1, None, title_es="", summary_es="<script>alert(1)</script>")
    html = _render([item], "data")
    assert "English title 1" in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_no_logo_file_falls_back_to_text(tmp_path, monkeypatch):
    monkeypatch.setattr(email_template, "LOGO_PATH", tmp_path / "nope.png")
    items = _items(tmp_path, 1)
    html = _render(items, "cid")
    assert "cid:winlogo" not in html
    assert [cid for _, cid in inline_images(items)] == ["card1"]


# --------------------------------------------------------------------------- #
# Outlook inline attachments (fake COM objects)
# --------------------------------------------------------------------------- #
class _FakeAccessor:
    def __init__(self, props: dict):
        self.props = props

    def SetProperty(self, tag, value):  # noqa: N802 - COM naming
        self.props[tag] = value


class _FakeAttachment:
    def __init__(self, source: str, fail: bool):
        if fail:
            raise RuntimeError("boom")
        self.source = source
        self.props: dict = {}
        self.PropertyAccessor = _FakeAccessor(self.props)


class _FakeAttachments:
    def __init__(self, fail_on: str = ""):
        self.items: list[_FakeAttachment] = []
        self.fail_on = fail_on

    def Add(self, Source, Type, Position, DisplayName):  # noqa: N802,N803 - COM naming
        att = _FakeAttachment(Source, fail=DisplayName == self.fail_on)
        self.items.append(att)
        return att


class _FakeMail:
    def __init__(self, fail_on: str = ""):
        self.Attachments = _FakeAttachments(fail_on)


def test_attach_inline_images_only_referenced_existing_files(tmp_path, logo, capsys):
    items = _items(tmp_path, 3)
    html = _render(items, "cid")
    images = inline_images(items) + [
        (str(tmp_path / "card0.png"), "unreferenced"),
        (str(tmp_path / "ghost.png"), "card3"),  # referenced cid but file missing
    ]
    mail = _FakeMail(fail_on="card2")

    attached = attach_inline_images(mail, html, images)

    assert attached == ["winlogo", "card1", "card3"]
    cids = [a.props[PR_ATTACH_CONTENT_ID] for a in mail.Attachments.items]
    assert cids == ["winlogo", "card1", "card3"]
    assert all(a.props[PR_ATTACH_HIDDEN] is True for a in mail.Attachments.items)
    assert "card2" in capsys.readouterr().out


def test_multiline_joke_keeps_line_breaks_and_escapes(tmp_path, logo):
    briefing = BRIEFING.model_copy(update={"chiste": "-Pregunta <b>?\n-Remate final."})
    html = render_email(briefing, _items(tmp_path), "gpt-x", "proj", "run-1", images="data", today=date(2026, 10, 20))
    assert "-Pregunta &lt;b&gt;?<br>-Remate final." in html
