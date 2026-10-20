"""HTML email template for the weekly WIN AI newsletter (all-staff audience).

Layout (600px, light theme, WIN palette), inspired by DataCamp's "This week in AI":

    header (WIN logo + "Noticias IA" + date + headline)
    -> "Concepto del día" box
    -> "Esta semana en IA": one card per news item (264px image left, text right)
    -> closing joke box
    -> footer

Outlook desktop (Word engine) safe: role="presentation" tables, inline styles,
`bgcolor`, fixed image `width`/`height` attributes and an `<!--[if mso]>` 600px
wrapper. A `@media (max-width:620px)` block stacks the card columns on phones
(Gmail app / iOS Mail honor it; Outlook desktop ignores it).

Images are referenced in one of two modes:
- ``"cid"``: ``cid:winlogo`` / ``cid:card<N>`` for sending; the sender attaches the
  files returned by :func:`inline_images` with those Content-IDs.
- ``"data"``: base64 data URIs, for the browser preview and the webapp iframe.
"""
from __future__ import annotations

import base64
import re
from datetime import date
from pathlib import Path
from typing import Literal

from jinja2 import Environment, select_autoescape
from markupsafe import Markup

from agente_noticias.config import LOGO_PATH
from agente_noticias.logos import display_name
from agente_noticias.schemas import Briefing, EvaluatedArticle

ImageMode = Literal["data", "cid"]

# WIN palette (brand book 2024).
ORANGE = "#FF5A0A"
YELLOW = "#FFC200"
BLACK = "#0F0908"
WHITE = "#FFFFFF"
SOFT_BG = "#FFF3EC"
PAGE_BG = "#F4F1EE"
TEXT_COLOR = "#1F2937"
MUTED_COLOR = "#6B7280"
FONT_STACK = Markup("'Poppins', 'Segoe UI', Arial, sans-serif")

WIN_LOGO_CID = "winlogo"
# Card PNGs are 528x370 (2x); they are displayed at 264x185.
CARD_IMG_WIDTH = 264
CARD_IMG_HEIGHT = 185

# Fallback card label when the evaluator left `label_es` empty.
CATEGORY_LABELS = {
    "Nuevos modelos": "Nuevo modelo",
    "IA agentica": "Agentes de IA",
    "Herramientas y productos": "Herramientas",
    "Investigacion": "Investigación",
    "Industria": "Industria",
}

MONTHS_ES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

_TRAILING_DATE = re.compile(r"\s*[-|·]\s*\d{4}-\d{2}-\d{2}\s*$")

TEMPLATE = """\
{%- macro label(text, color) -%}
<p style="margin:0 0 8px 0;font-family:{{ font }};font-size:12px;font-weight:600;line-height:1.25;letter-spacing:1.5px;text-transform:uppercase;color:{{ color }};">{{ text }}</p>
{%- endmacro -%}

{%- macro news_card(c, last) -%}
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
  <tr>
    {%- if c.img_src %}
    <td class="card-img" width="{{ img_w }}" valign="top" style="width:{{ img_w }}px;padding-right:16px;vertical-align:top;">
      <a href="{{ c.url }}" target="_blank" style="display:block;border:0;text-decoration:none;line-height:0;font-size:0;">
        <img src="{{ c.img_src }}" width="{{ img_w }}" height="{{ img_h }}" alt="{{ c.title }}"
             style="display:block;width:{{ img_w }}px;max-width:100%;height:auto;border:0;border-radius:8px;">
      </a>
    </td>
    {%- endif %}
    <td class="card-txt" valign="top" style="vertical-align:top;">
      {{ label(c.label, muted) }}
      <p style="margin:0 0 8px 0;font-family:{{ font }};font-size:18px;font-weight:600;line-height:1.3;color:{{ black }};">
        <a href="{{ c.url }}" target="_blank" style="color:{{ black }};text-decoration:none;">{{ c.title }}</a>
      </p>
      <p style="margin:0 0 8px 0;font-family:{{ font }};font-size:16px;font-weight:400;line-height:1.5;color:{{ text }};">{{ c.summary }}</p>
      <a href="{{ c.url }}" target="_blank" style="font-family:{{ font }};font-size:16px;font-weight:600;line-height:1.5;color:{{ orange }};text-decoration:none;"><span style="color:{{ orange }};font-weight:600;text-decoration:none;">Leer más &rarr;</span></a>
    </td>
  </tr>
  {%- if not last %}
  <tr><td{% if c.img_src %} colspan="2"{% endif %} height="40" style="height:40px;font-size:1px;line-height:1px;">&nbsp;</td></tr>
  {%- endif %}
</table>
{%- endmacro -%}

<!DOCTYPE html>
<html lang="es" xmlns="http://www.w3.org/1999/xhtml" xmlns:o="urn:schemas-microsoft-com:office:office">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="x-apple-disable-message-reformatting">
<meta name="color-scheme" content="light">
<meta name="supported-color-schemes" content="light">
<title>{{ headline }}</title>
<!--[if mso]>
<noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript>
<style>table, td, p, a, span, div { font-family: 'Segoe UI', Arial, sans-serif !important; }</style>
<![endif]-->
<!--[if !mso]><!-->
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
<!--<![endif]-->
<style>
  body { margin:0; padding:0; -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }
  table, td { border-collapse:collapse; mso-table-lspace:0pt; mso-table-rspace:0pt; }
  img { border:0; outline:none; text-decoration:none; -ms-interpolation-mode:bicubic; }
  @media (max-width:620px) {
    .container { width:100% !important; max-width:100% !important; border-radius:0 !important; }
    .px { padding-left:16px !important; padding-right:16px !important; }
    .card-img, .card-txt { display:block !important; width:100% !important; max-width:100% !important; }
    .card-img { padding:0 0 16px 0 !important; }
    .card-img img { width:100% !important; max-width:100% !important; height:auto !important; }
    .headline { font-size:22px !important; }
  }
</style>
</head>
<body style="margin:0;padding:0;background-color:{{ page_bg }};" bgcolor="{{ page_bg }}">
<div style="display:none;max-height:0;max-width:0;overflow:hidden;mso-hide:all;font-size:1px;line-height:1px;color:{{ page_bg }};opacity:0;">{{ preheader }}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{{ page_bg }}" style="background-color:{{ page_bg }};">
  <tr><td align="center" style="padding:24px 0;">
<!--[if mso]><table role="presentation" width="600" cellpadding="0" cellspacing="0" border="0" align="center"><tr><td width="600"><![endif]-->
    <table role="presentation" class="container" width="600" cellpadding="0" cellspacing="0" border="0" align="center" bgcolor="{{ white }}"
           style="width:100%;max-width:600px;background-color:{{ white }};border-radius:12px;">

      <!-- header -->
      <tr>
        <td class="px" bgcolor="{{ orange }}" style="background-color:{{ orange }};padding:24px 24px 28px 24px;border-radius:12px 12px 0 0;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td align="left" valign="middle" style="vertical-align:middle;">
                {%- if logo_src %}
                <img src="{{ logo_src }}" width="72" height="72" alt="WIN" style="display:block;width:72px;height:72px;border:0;">
                {%- else %}
                <span style="font-family:{{ font }};font-size:40px;font-weight:700;color:{{ white }};">win</span>
                {%- endif %}
              </td>
              <td align="right" valign="middle" style="vertical-align:middle;font-family:{{ font }};font-size:13px;line-height:1.4;color:#FFE6D5;">
                {{ today }}
              </td>
            </tr>
          </table>
          <p style="margin:16px 0 4px 0;font-family:{{ font }};font-size:12px;font-weight:600;line-height:1.25;letter-spacing:1.5px;text-transform:uppercase;color:#FFE6D5;">Noticias IA</p>
          <p class="headline" style="margin:0;font-family:{{ font }};font-size:24px;font-weight:700;line-height:1.3;color:{{ white }};">{{ headline }}</p>
        </td>
      </tr>

      {%- if briefing.concepto_titulo %}
      <!-- concepto del dia -->
      <tr>
        <td class="px" style="padding:32px 24px 0 24px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{{ soft_bg }}"
                 style="background-color:{{ soft_bg }};border-left:4px solid {{ orange }};border-radius:12px;">
            <tr>
              <td style="padding:20px 20px 20px 20px;">
                {{ label("Concepto del día", orange) }}
                <p style="margin:0 0 6px 0;font-family:{{ font }};font-size:18px;font-weight:600;line-height:1.3;color:{{ black }};">{{ briefing.concepto_titulo }}</p>
                <p style="margin:0;font-family:{{ font }};font-size:16px;font-weight:400;line-height:1.5;color:{{ text }};">{{ briefing.concepto_explicacion }}</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      {%- endif %}

      {%- if cards %}
      <!-- esta semana en IA -->
      <tr>
        <td class="px" style="padding:40px 24px 24px 24px;">
          <p style="margin:0 0 10px 0;font-family:{{ font }};font-size:24px;font-weight:700;line-height:1.25;color:{{ black }};">Esta semana en IA</p>
          <table role="presentation" width="48" cellpadding="0" cellspacing="0" border="0">
            <tr><td width="48" height="4" bgcolor="{{ orange }}" style="width:48px;height:4px;font-size:1px;line-height:1px;background-color:{{ orange }};">&nbsp;</td></tr>
          </table>
        </td>
      </tr>
      {%- for c in cards %}
      <tr>
        <td class="px" style="padding:0 24px;">
          {{ news_card(c, loop.last) }}
        </td>
      </tr>
      {%- endfor %}
      {%- endif %}

      {%- if briefing.chiste %}
      <!-- chiste -->
      <tr>
        <td class="px" style="padding:40px 24px 0 24px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="{{ black }}"
                 style="background-color:{{ black }};border-radius:12px;">
            <tr>
              <td style="padding:20px 20px 20px 20px;">
                {{ label("Para cerrar con humor winner", yellow) }}
                <p style="margin:0;font-family:{{ font }};font-size:16px;font-weight:400;line-height:1.5;color:{{ white }};">{{ briefing.chiste }}</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      {%- endif %}

      <!-- footer -->
      <tr>
        <td class="px" style="padding:32px 24px 32px 24px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr><td height="1" bgcolor="#F0E0D5" style="height:1px;font-size:1px;line-height:1px;background-color:#F0E0D5;">&nbsp;</td></tr>
          </table>
          <p style="margin:20px 0 6px 0;font-family:{{ font }};font-size:16px;font-weight:700;line-height:1.4;color:{{ orange }};">Mente y actitud winner!</p>
          <p style="margin:0;font-family:{{ font }};font-size:12px;font-weight:400;line-height:1.5;color:{{ muted }};">
            Boletín interno de WIN Internet para todo el equipo. Las noticias se seleccionan y resumen con ayuda de IA; cada tarjeta enlaza a la fuente original.
          </p>
        </td>
      </tr>

    </table>
<!--[if mso]></td></tr></table><![endif]-->
  </td></tr>
</table>
<!-- agente-noticias model={{ model }} project={{ project }} run_id={{ run_id }} -->
</body>
</html>
"""

_ENV = Environment(autoescape=select_autoescape(default_for_string=True, default=True))
_TEMPLATE = _ENV.from_string(TEMPLATE)


def file_data_uri(path: Path | str | None, mime: str = "image/png") -> str:
    """Base64 data URI of a file ('' if it is missing or unreadable)."""
    if not path:
        return ""
    try:
        data = Path(path).read_bytes()
    except OSError:
        return ""
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def logo_data_uri() -> str:
    """WIN logo as a data URI (browser preview)."""
    return file_data_uri(LOGO_PATH)


def card_cid(index: int) -> str:
    """Content-ID of the card image at 0-based `index`."""
    return f"card{index + 1}"


def _card_path(item: EvaluatedArticle) -> Path | None:
    if not item.card_image_path:
        return None
    path = Path(item.card_image_path)
    return path if path.is_file() else None


def inline_images(selected: list[EvaluatedArticle]) -> list[tuple[str, str]]:
    """(path, cid) of every image the "cid" render references, for the sender to attach."""
    images: list[tuple[str, str]] = []
    if LOGO_PATH.is_file():
        images.append((str(LOGO_PATH), WIN_LOGO_CID))
    for i, item in enumerate(selected):
        path = _card_path(item)
        if path is not None:
            images.append((str(path), card_cid(i)))
    return images


def card_label(item: EvaluatedArticle) -> str:
    """Upper-case card kicker, e.g. 'LANZAMIENTO · OPENAI'."""
    e = item.evaluation
    label = (e.label_es or "").strip() or CATEGORY_LABELS.get(e.category, e.category)
    parts = [label]
    if e.company:
        parts.append(display_name(e.company))
    return " · ".join(p for p in parts if p).upper()


def display_headline(headline: str) -> str:
    """Headline without the trailing ' - YYYY-MM-DD' (the header shows the date)."""
    return _TRAILING_DATE.sub("", headline or "").strip()


def spanish_date(d: date) -> str:
    return f"{d.day} de {MONTHS_ES[d.month - 1]} de {d.year}"


def _card_view(item: EvaluatedArticle, index: int, images: ImageMode) -> dict:
    a, e = item.article, item.evaluation
    path = _card_path(item)
    if path is None:
        img_src = ""
    elif images == "cid":
        img_src = f"cid:{card_cid(index)}"
    else:
        img_src = file_data_uri(path)
    return {
        "url": a.url,
        "title": (e.title_es or "").strip() or a.title,
        "summary": e.summary_es,
        "label": card_label(item),
        "img_src": img_src,
    }


def render_email(
    briefing: Briefing,
    selected: list[EvaluatedArticle],
    model: str = "",
    project: str = "",
    run_id: str = "",
    *,
    images: ImageMode = "data",
    today: date | None = None,
) -> str:
    """Renders the newsletter HTML.

    `images="cid"` references `cid:` Content-IDs (attach `inline_images(selected)`
    when sending); `images="data"` embeds base64 data URIs (browser preview).
    """
    if images == "cid":
        logo_src = f"cid:{WIN_LOGO_CID}" if LOGO_PATH.is_file() else ""
    else:
        logo_src = logo_data_uri()
    cards = [_card_view(item, i, images) for i, item in enumerate(selected)]
    headline = display_headline(briefing.headline)
    preheader = cards[0]["title"] if cards else headline
    return _TEMPLATE.render(
        briefing=briefing,
        headline=headline,
        preheader=preheader,
        cards=cards,
        today=spanish_date(today or date.today()),
        logo_src=logo_src,
        img_w=CARD_IMG_WIDTH,
        img_h=CARD_IMG_HEIGHT,
        font=FONT_STACK,
        orange=ORANGE,
        yellow=YELLOW,
        black=BLACK,
        white=WHITE,
        soft_bg=SOFT_BG,
        page_bg=PAGE_BG,
        text=TEXT_COLOR,
        muted=MUTED_COLOR,
        model=model,
        project=project,
        run_id=run_id,
    )
