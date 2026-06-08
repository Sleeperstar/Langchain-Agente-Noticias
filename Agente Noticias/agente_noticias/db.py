"""Cliente Supabase para el historial anti-repeticion de noticias.

Usa el esquema dedicado `agente_noticias` (tablas `briefings` y `sent_articles`)
en el proyecto Supabase configurado via SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY.

Si las credenciales no estan configuradas, las funciones degradan de forma segura
(no filtran ni persisten) para que el agente siga funcionando.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from agente_noticias.config import get_supabase_config

SCHEMA = "agente_noticias"


def get_client():
    """Devuelve un cliente Supabase o None si no hay credenciales."""
    url, key = get_supabase_config()
    if not url or not key:
        return None
    try:
        from supabase import create_client

        return create_client(url, key)
    except Exception as exc:  # noqa: BLE001
        print(f"[db] no se pudo crear el cliente Supabase: {exc}")
        return None


def fetch_recent_sent(weeks: int) -> list[dict]:
    """Devuelve [{url, normalized_title}] de noticias enviadas en las ultimas `weeks` semanas."""
    client = get_client()
    if client is None:
        return []

    since = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).isoformat()
    try:
        resp = (
            client.schema(SCHEMA)
            .table("sent_articles")
            .select("url, normalized_title")
            .gte("sent_at", since)
            .execute()
        )
        return resp.data or []
    except Exception as exc:  # noqa: BLE001
        print(f"[db] fallo consultando historial: {exc}")
        return []


def fetch_recent_jokes(weeks: int) -> list[str]:
    """Devuelve los chistes enviados en las ultimas `weeks` semanas (texto)."""
    client = get_client()
    if client is None:
        return []

    since = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).isoformat()
    try:
        resp = (
            client.schema(SCHEMA)
            .table("briefings")
            .select("joke")
            .gte("sent_at", since)
            .execute()
        )
        return [row.get("joke", "") for row in (resp.data or []) if row.get("joke")]
    except Exception as exc:  # noqa: BLE001
        print(f"[db] fallo consultando chistes: {exc}")
        return []


def fetch_recent_concepts(weeks: int) -> list[str]:
    """Devuelve los titulos de 'concepto del dia' usados en las ultimas `weeks` semanas."""
    client = get_client()
    if client is None:
        return []

    since = (datetime.now(timezone.utc) - timedelta(weeks=weeks)).isoformat()
    try:
        resp = (
            client.schema(SCHEMA)
            .table("briefings")
            .select("concepto_titulo")
            .gte("sent_at", since)
            .execute()
        )
        return [
            row.get("concepto_titulo", "")
            for row in (resp.data or [])
            if row.get("concepto_titulo")
        ]
    except Exception as exc:  # noqa: BLE001
        # Probablemente la columna aun no existe (migracion pendiente): degradamos.
        print(f"[db] fallo consultando conceptos: {exc}")
        return []


def save_briefing(
    subject: str,
    recipients: str,
    run_id: str,
    langsmith_project: str,
    articles: list[dict],
    joke: str = "",
    joke_normalized: str = "",
    concepto_titulo: str = "",
    concepto_explicacion: str = "",
    concepto_normalized: str = "",
) -> str:
    """Inserta un briefing y sus articulos. Devuelve el briefing_id o '' si fallo.

    `articles` es una lista de dicts con: url, normalized_title, title, source,
    category, relevance_score, published_date.
    """
    client = get_client()
    if client is None:
        return ""

    now = datetime.now(timezone.utc)
    week_iso = f"{now.isocalendar().year}-W{now.isocalendar().week:02d}"

    base_row = {
        "subject": subject,
        "recipients": recipients,
        "run_id": run_id,
        "article_count": len(articles),
        "langsmith_project": langsmith_project,
        "joke": joke,
        "joke_normalized": joke_normalized,
    }
    concept_row = {
        "concepto_titulo": concepto_titulo,
        "concepto_explicacion": concepto_explicacion,
        "concepto_normalized": concepto_normalized,
    }

    try:
        try:
            briefing_resp = (
                client.schema(SCHEMA)
                .table("briefings")
                .insert({**base_row, **concept_row})
                .execute()
            )
        except Exception as exc:  # noqa: BLE001
            # Si las columnas del concepto aun no existen (migracion pendiente),
            # reintentamos sin ellas para no perder el historial de noticias/chiste.
            print(f"[db] insert con concepto fallo ({exc}); reintento sin concepto")
            briefing_resp = (
                client.schema(SCHEMA)
                .table("briefings")
                .insert(base_row)
                .execute()
            )
        briefing_id = (briefing_resp.data or [{}])[0].get("id", "")
        if not briefing_id:
            return ""

        rows = []
        for a in articles:
            rows.append(
                {
                    "briefing_id": briefing_id,
                    "url": a.get("url", ""),
                    "normalized_title": a.get("normalized_title", ""),
                    "title": a.get("title", ""),
                    "source": a.get("source", ""),
                    "category": a.get("category", ""),
                    "relevance_score": int(a.get("relevance_score", 0) or 0),
                    "published_date": a.get("published_date", ""),
                    "week_iso": week_iso,
                }
            )
        if rows:
            client.schema(SCHEMA).table("sent_articles").insert(rows).execute()

        return str(briefing_id)
    except Exception as exc:  # noqa: BLE001
        print(f"[db] fallo guardando historial: {exc}")
        return ""
