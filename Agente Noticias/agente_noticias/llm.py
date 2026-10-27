"""Single factory for the text LLM: every chat call goes through OpenRouter.

OpenRouter exposes an OpenAI-compatible API, so we reuse `ChatOpenAI` (via
`init_chat_model(..., model_provider="openai")`) pointed at OpenRouter's base URL.
`with_structured_output(Schema)` keeps langchain-openai's default
`method="json_schema"`; with a Pydantic schema the OpenAI SDK sends a strict
JSON schema (`strict: true`), the same semantics as calling OpenAI directly.
"""
from __future__ import annotations

import os

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

from agente_noticias.config import get_model

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
# Optional OpenRouter app attribution headers (shown in the OpenRouter dashboard).
OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://win.pe",
    "X-Title": "Agente Noticias WIN",
}


class MissingOpenRouterKeyError(RuntimeError):
    """Raised when OPENROUTER_API_KEY is not configured."""


def get_openrouter_api_key() -> str:
    """OPENROUTER_API_KEY from the environment; fails fast with a clear message."""
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise MissingOpenRouterKeyError(
            "OPENROUTER_API_KEY no esta configurada. Agregala al .env del proyecto: "
            "todas las llamadas de texto (y las imagenes) usan OpenRouter."
        )
    return api_key


def get_chat_model(model: str | None = None) -> BaseChatModel:
    """Chat model (OpenRouter id, e.g. `openai/gpt-5-mini`) routed through OpenRouter."""
    return init_chat_model(
        model or get_model(),
        model_provider="openai",
        base_url=OPENROUTER_BASE_URL,
        api_key=get_openrouter_api_key(),
        default_headers=OPENROUTER_HEADERS,
    )
