"""Plantilla HTML compatible con Outlook (motor Word: tablas + CSS inline)."""
from __future__ import annotations

from collections import OrderedDict
from datetime import date
from typing import Iterable

from jinja2 import Environment, select_autoescape

from agente_noticias.schemas import Briefing, EvaluatedArticle

PRIMARY_COLOR = "#003B7A"
ACCENT_COLOR = "#00A6CE"
SOFT_BG = "#F4F7FB"
TEXT_COLOR = "#1F2937"
MUTED_COLOR = "#6B7280"

TEMPLATE = """\
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>{{ briefing.headline }}</title>
</head>
<body style="margin:0;padding:0;background:#E5E9F0;font-family:Segoe UI,Arial,sans-serif;color:{{ text }};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#E5E9F0">
  <tr><td align="center" style="padding:24px 12px;">

    <!-- contenedor -->
    <table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0"
           style="width:640px;max-width:640px;background:#FFFFFF;border-radius:8px;overflow:hidden;
                  box-shadow:0 2px 6px rgba(0,0,0,0.08);">

      <!-- header -->
      <tr>
        <td bgcolor="{{ primary }}" style="padding:24px 28px;color:#FFFFFF;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
            <tr>
              <td style="font-size:12px;letter-spacing:2px;color:#B9D7F2;text-transform:uppercase;">
                Briefing IA - Win Internet
              </td>
              <td align="right" style="font-size:12px;color:#B9D7F2;">{{ today }}</td>
            </tr>
            <tr>
              <td colspan="2" style="padding-top:8px;font-size:22px;font-weight:600;line-height:1.3;color:#FFFFFF;">
                {{ briefing.headline }}
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- TL;DR -->
      <tr>
        <td style="padding:24px 28px 8px 28px;">
          <div style="font-size:11px;letter-spacing:1.5px;color:{{ accent }};
                      text-transform:uppercase;font-weight:700;">Lectura de 30 segundos</div>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                 style="margin-top:10px;background:{{ soft_bg }};border-radius:6px;">
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
          <div style="font-size:13px;letter-spacing:1px;color:{{ primary }};
                      text-transform:uppercase;font-weight:700;border-bottom:2px solid {{ accent }};
                      padding-bottom:6px;">
            {{ area }}
          </div>
        </td>
      </tr>
      {% for item in items %}
      <tr>
        <td style="padding:14px 28px 0 28px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
                 style="border:1px solid #E1E7F0;border-radius:6px;">
            <tr>
              <td style="padding:14px 16px 6px 16px;">
                <a href="{{ item.article.url }}"
                   style="color:{{ primary }};text-decoration:none;font-weight:600;font-size:16px;line-height:1.35;">
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
                       style="background:{{ soft_bg }};border-left:3px solid {{ accent }};">
                  <tr>
                    <td style="padding:10px 12px;font-size:13px;line-height:1.5;color:{{ text }};">
                      <strong style="color:{{ primary }};">Por que importa a Win:</strong>
                      {{ item.evaluation.why_matters_for_win }}
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
                        bgcolor="{% if n <= item.evaluation.relevance_score %}{{ accent }}{% else %}#DCE3ED{% endif %}"
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

      <!-- footer -->
      <tr>
        <td style="padding:24px 28px 28px 28px;">
          <hr style="border:0;border-top:1px solid #E1E7F0;margin:0 0 12px 0;">
          <div style="font-size:12px;color:{{ muted }};line-height:1.5;">
            Generado automaticamente por <strong>Agente Noticias Win Internet</strong>
            con LangChain + LangGraph + Tavily.<br>
            Modelo: {{ model }} &middot; Proyecto LangSmith:
            <span style="color:{{ primary }};">{{ project }}</span>
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


def _group_by_area(items: Iterable[EvaluatedArticle]) -> list[tuple[str, list[EvaluatedArticle]]]:
    """Agrupa articulos por la primera area de impacto declarada."""
    grouped: OrderedDict[str, list[EvaluatedArticle]] = OrderedDict()
    for it in items:
        area = it.evaluation.impact_areas[0] if it.evaluation.impact_areas else "Mercado y Negocio"
        grouped.setdefault(area, []).append(it)
    return list(grouped.items())


def render_email(
    briefing: Briefing,
    selected: list[EvaluatedArticle],
    model: str,
    project: str,
    run_id: str = "",
) -> str:
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    template = env.from_string(TEMPLATE)
    return template.render(
        briefing=briefing,
        grouped=_group_by_area(selected),
        today=date.today().strftime("%d/%m/%Y"),
        primary=PRIMARY_COLOR,
        accent=ACCENT_COLOR,
        soft_bg=SOFT_BG,
        text=TEXT_COLOR,
        muted=MUTED_COLOR,
        model=model,
        project=project,
        run_id=run_id,
    )
