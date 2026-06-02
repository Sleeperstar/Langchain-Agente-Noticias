"""Plantilla HTML del correo con el look and feel de Win Internet.

Compatible con Outlook (motor Word: tablas + CSS inline). Paleta oficial del
brand book: naranja principal, negro, blanco y amarillo de resalte.
"""
from __future__ import annotations

import base64
from collections import OrderedDict
from datetime import date
from typing import Iterable

from jinja2 import Environment, select_autoescape

from agente_noticias.config import CATEGORIAS, LOGO_PATH
from agente_noticias.schemas import Briefing, EvaluatedArticle

# Paleta oficial Win (brand book 2024).
ORANGE = "#FF5A0A"
YELLOW = "#FFC200"
BLACK = "#0F0908"
WHITE = "#FFFFFF"
SOFT_BG = "#FFF3EC"
TEXT_COLOR = "#1F2937"
MUTED_COLOR = "#6B7280"

TEMPLATE = """\
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>{{ briefing.headline }}</title>
</head>
<body style="margin:0;padding:0;background:#ECECEC;font-family:Segoe UI,Arial,sans-serif;color:{{ text }};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#ECECEC">
  <tr><td align="center" style="padding:24px 12px;">

    <!-- contenedor -->
    <table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0"
           style="width:640px;max-width:640px;background:#FFFFFF;border-radius:10px;overflow:hidden;
                  box-shadow:0 2px 8px rgba(0,0,0,0.10);">

      <!-- header -->
      <tr>
        <td bgcolor="{{ orange }}" style="padding:22px 28px;color:#FFFFFF;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td align="left" style="vertical-align:middle;">
                {% if logo_src %}
                <img src="{{ logo_src }}" alt="WIN" height="34" style="height:34px;display:block;border:0;">
                {% else %}
                <span style="font-size:30px;font-weight:800;color:#FFFFFF;letter-spacing:-1px;">win</span>
                {% endif %}
              </td>
              <td align="right" style="vertical-align:middle;font-size:12px;color:#FFE6D5;">
                {{ today }}
              </td>
            </tr>
          </table>
          <div style="margin-top:14px;font-size:11px;letter-spacing:2px;color:#FFE6D5;text-transform:uppercase;">
            Briefing semanal de IA
          </div>
          <div style="margin-top:4px;font-size:22px;font-weight:700;line-height:1.3;color:#FFFFFF;">
            {{ briefing.headline }}
          </div>
        </td>
      </tr>

      <!-- concepto del dia -->
      {% if briefing.concepto_titulo %}
      <tr>
        <td style="padding:20px 28px 4px 28px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                 style="background:{{ yellow }};border-radius:8px;">
            <tr>
              <td style="padding:14px 18px;color:{{ black }};">
                <div style="font-size:11px;letter-spacing:1.5px;text-transform:uppercase;font-weight:800;">
                  Concepto del dia
                </div>
                <div style="margin-top:6px;font-size:16px;font-weight:700;">{{ briefing.concepto_titulo }}</div>
                <div style="margin-top:4px;font-size:14px;line-height:1.55;">{{ briefing.concepto_explicacion }}</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      {% endif %}

      <!-- TL;DR -->
      <tr>
        <td style="padding:18px 28px 8px 28px;">
          <div style="font-size:11px;letter-spacing:1.5px;color:{{ orange }};
                      text-transform:uppercase;font-weight:800;">Lectura de 30 segundos</div>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                 style="margin-top:10px;background:{{ soft_bg }};border-radius:8px;">
            <tr>
              <td style="padding:16px 18px;font-size:15px;line-height:1.55;color:{{ text }};">
                <ul style="margin:0;padding:0 0 0 18px;">
                  {% for bullet in briefing.tldr %}
                    <li style="margin-bottom:6px;">{{ bullet }}</li>
                  {% endfor %}
                </ul>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- secciones por categoria -->
      {% for area, items in grouped %}
      <tr>
        <td style="padding:18px 28px 0 28px;">
          <div style="font-size:13px;letter-spacing:1px;color:{{ black }};
                      text-transform:uppercase;font-weight:800;border-bottom:3px solid {{ orange }};
                      padding-bottom:6px;">
            {{ area }}
          </div>
        </td>
      </tr>
      {% for item in items %}
      <tr>
        <td style="padding:14px 28px 0 28px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                 style="border:1px solid #F0E0D5;border-radius:8px;">
            <tr>
              <td style="padding:14px 16px 6px 16px;">
                <a href="{{ item.article.url }}"
                   style="color:{{ black }};text-decoration:none;font-weight:700;font-size:16px;line-height:1.35;">
                  {{ item.article.title }}
                </a>
                <div style="margin-top:4px;font-size:12px;color:{{ muted }};">
                  {{ item.article.source or 'fuente' }}{% if item.article.published_date %} &middot; {{ item.article.published_date }}{% endif %}
                </div>
              </td>
            </tr>
            <tr>
              <td style="padding:0 16px 8px 16px;font-size:14px;line-height:1.55;color:{{ text }};">
                {{ item.evaluation.summary_es }}
              </td>
            </tr>
            <tr>
              <td style="padding:6px 16px 6px 16px;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                       style="background:{{ soft_bg }};border-left:3px solid {{ orange }};">
                  <tr>
                    <td style="padding:10px 12px;font-size:13px;line-height:1.5;color:{{ text }};">
                      <strong style="color:{{ orange }};">En simple:</strong>
                      {{ item.evaluation.en_simple }}
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            <tr>
              <td style="padding:6px 16px 14px 16px;">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0">
                  <tr>
                    <td style="font-size:11px;color:{{ muted }};padding-right:10px;">Relevancia</td>
                    {% for n in range(1, 11) %}
                    <td width="14" height="10"
                        bgcolor="{% if n <= item.evaluation.relevance_score %}{{ orange }}{% else %}#EADFD6{% endif %}"
                        style="font-size:0;line-height:0;padding:0 1px;">&nbsp;</td>
                    {% endfor %}
                    <td style="font-size:11px;color:{{ muted }};padding-left:8px;">
                      {{ item.evaluation.relevance_score }}/10
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      {% endfor %}
      {% endfor %}

      <!-- chiste -->
      {% if briefing.chiste %}
      <tr>
        <td style="padding:20px 28px 4px 28px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                 style="background:{{ black }};border-radius:8px;">
            <tr>
              <td style="padding:16px 18px;color:#FFFFFF;">
                <div style="font-size:11px;letter-spacing:1.5px;text-transform:uppercase;font-weight:800;color:{{ yellow }};">
                  Para cerrar con humor winner
                </div>
                <div style="margin-top:6px;font-size:15px;line-height:1.55;">{{ briefing.chiste }}</div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      {% endif %}

      <!-- footer -->
      <tr>
        <td style="padding:22px 28px 26px 28px;">
          <hr style="border:0;border-top:1px solid #F0E0D5;margin:0 0 12px 0;">
          <div style="font-size:15px;font-weight:800;color:{{ orange }};">Mente y actitud winner!</div>
          <div style="margin-top:8px;font-size:12px;color:{{ muted }};line-height:1.5;">
            Generado automaticamente por el <strong>Agente Noticias IA de Win</strong>
            con LangChain + LangGraph + Tavily.<br>
            Modelo: {{ model }} &middot; Proyecto LangSmith:
            <span style="color:{{ orange }};">{{ project }}</span>
            {% if run_id %} &middot; run_id: <code style="font-size:11px;">{{ run_id }}</code>{% endif %}
          </div>
        </td>
      </tr>

    </table>
    <!-- /contenedor -->

  </td></tr>
</table>
</body>
</html>
"""


def _group_by_category(
    items: Iterable[EvaluatedArticle],
) -> list[tuple[str, list[EvaluatedArticle]]]:
    """Agrupa articulos por categoria, respetando el orden de CATEGORIAS."""
    grouped: OrderedDict[str, list[EvaluatedArticle]] = OrderedDict(
        (cat, []) for cat in CATEGORIAS
    )
    for it in items:
        area = it.evaluation.category or "Industria"
        grouped.setdefault(area, []).append(it)
    return [(area, its) for area, its in grouped.items() if its]


def logo_data_uri() -> str:
    """Devuelve el logo como data URI base64 (para el preview en navegador)."""
    try:
        if LOGO_PATH.exists():
            data = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
            return f"data:image/png;base64,{data}"
    except Exception:  # noqa: BLE001
        pass
    return ""


def render_email(
    briefing: Briefing,
    selected: list[EvaluatedArticle],
    model: str,
    project: str,
    run_id: str = "",
    logo_src: str = "",
) -> str:
    """Renderiza el correo. `logo_src` es el src del logo (data URI o cid:winlogo)."""
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    template = env.from_string(TEMPLATE)
    return template.render(
        briefing=briefing,
        grouped=_group_by_category(selected),
        today=date.today().strftime("%d/%m/%Y"),
        orange=ORANGE,
        yellow=YELLOW,
        black=BLACK,
        soft_bg=SOFT_BG,
        text=TEXT_COLOR,
        muted=MUTED_COLOR,
        model=model,
        project=project,
        run_id=run_id,
        logo_src=logo_src,
    )
