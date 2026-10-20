"""Company logo library for the newsletter card badge.

Keys are the canonical `schemas.CompanyKey` values returned by the evaluator. Logos
are transparent PNGs in `assets/logos/<key>.png` (see assets/logos/README.md).
"""
from __future__ import annotations

from pathlib import Path

from agente_noticias.config import COMPANY_LOGOS_DIR

COMPANY_DISPLAY_NAMES: dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "gemini": "Gemini",
    "meta": "Meta",
    "microsoft": "Microsoft",
    "nvidia": "NVIDIA",
    "xai": "xAI",
    "mistral": "Mistral AI",
    "deepseek": "DeepSeek",
    "apple": "Apple",
    "amazon": "Amazon",
    "alibaba": "Alibaba",
    "qwen": "Qwen",
}


def display_name(company: str) -> str:
    """Human name shown in the badge (falls back to the key itself)."""
    return COMPANY_DISPLAY_NAMES.get(company, company)


def logo_path(company: str, logos_dir: Path | None = None) -> Path | None:
    """Path of the company logo PNG, or None if it is not in the library."""
    path = (logos_dir or COMPANY_LOGOS_DIR) / f"{company}.png"
    return path if path.is_file() else None
