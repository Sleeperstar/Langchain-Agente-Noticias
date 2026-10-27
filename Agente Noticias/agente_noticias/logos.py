"""Company names, slugs and logo library for the newsletter card badge.

The evaluator returns any company name (or null). `canonical_company` maps the 14 key
companies (priority + built-in logos) to their key and keeps any other company as its
cleaned display name; `company_slug` gives the filesystem/diversity key of either.

Logo lookup: built-in `assets/logos/<key>.png` first, then logos learned at runtime by
`logo_finder` in `data/logos/<slug>.png` (registry: `data/logos/registry.json`).
"""
from __future__ import annotations

import json
import os
import re
import threading
import unicodedata
from pathlib import Path

from agente_noticias.config import COMPANY_LOGOS_DIR, LEARNED_LOGOS_DIR

# Key companies: prioritized by the ranker and shipped with a built-in logo.
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
KEY_COMPANIES = frozenset(COMPANY_DISPLAY_NAMES)

# Slugified aliases -> key (the keys themselves are matched directly).
_ALIASES: dict[str, str] = {
    "open-ai": "openai",
    "chatgpt": "openai",
    "anthropic-pbc": "anthropic",
    "claude": "anthropic",
    "google-deepmind": "google",
    "deepmind": "google",
    "alphabet": "google",
    "google-cloud": "google",
    "google-research": "google",
    "google-gemini": "gemini",
    "meta-ai": "meta",
    "meta-platforms": "meta",
    "facebook": "meta",
    "meta-superintelligence-labs": "meta",
    "microsoft-ai": "microsoft",
    "x-ai": "xai",
    "grok": "xai",
    "mistral-ai": "mistral",
    "mistralai": "mistral",
    "deepseek-ai": "deepseek",
    "aws": "amazon",
    "amazon-web-services": "amazon",
    "amazon-com": "amazon",
    "alibaba-cloud": "alibaba",
    "alibaba-group": "alibaba",
}

# Trailing legal forms dropped from the slug ("Walmart Inc." -> "walmart").
_LEGAL_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "ltd", "limited", "llc", "plc",
    "gmbh", "ag", "sa", "sac", "nv", "bv", "co",
}
MAX_COMPANY_CHARS = 60

REGISTRY_NAME = "registry.json"
_registry_lock = threading.Lock()


def slugify(value: str) -> str:
    """ASCII, lowercase, hyphen-separated slug (empty string if nothing is left)."""
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_value.lower()).strip("-")


def _strip_legal_suffixes(parts: list[str]) -> list[str]:
    """Drops trailing legal forms, also when dotted ("S.A." -> ["s", "a"])."""
    while len(parts) > 1:
        if parts[-1] in _LEGAL_SUFFIXES:
            parts = parts[:-1]
            continue
        letters = 0
        while letters < len(parts) - 1 and len(parts[-1 - letters]) == 1:
            letters += 1
        if letters >= 2 and "".join(parts[-letters:]) in _LEGAL_SUFFIXES:
            parts = parts[:-letters]
            continue
        break
    return parts


def company_slug(company: str | None) -> str | None:
    """Stable key of a company: a key-company key or a slug of its name (None if blank)."""
    if not company or not company.strip():
        return None
    slug = slugify(company)
    slug = "-".join(_strip_legal_suffixes(slug.split("-")))
    if not slug:
        return None
    if slug in KEY_COMPANIES:
        return slug
    return _ALIASES.get(slug, slug)


def is_key_company(company: str | None) -> bool:
    return company_slug(company) in KEY_COMPANIES


def canonical_company(company: str | None) -> str | None:
    """Value stored in `ArticleEvaluation.company`: key for key companies, else the name.

    Idempotent, so drafts saved earlier (keys or names) load back unchanged.
    """
    slug = company_slug(company)
    if slug is None:
        return None
    if slug in KEY_COMPANIES:
        return slug
    return " ".join(company.split())[:MAX_COMPANY_CHARS]


# --------------------------------------------------------------------------- #
# Learned-logo registry (data/logos/registry.json)
# --------------------------------------------------------------------------- #
def learned_logos_dir() -> Path:
    return LEARNED_LOGOS_DIR


def registry_path() -> Path:
    return learned_logos_dir() / REGISTRY_NAME


def load_registry() -> dict[str, dict]:
    """slug -> entry; an unreadable registry counts as empty."""
    path = registry_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def update_registry(slug: str, entry: dict) -> None:
    """Sets one registry entry (thread-safe, atomic replace)."""
    with _registry_lock:
        data = load_registry()
        data[slug] = entry
        path = registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(f".{os.getpid()}.{threading.get_ident()}.tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)


def display_name(company: str) -> str:
    """Human name shown in the badge / email label."""
    slug = company_slug(company)
    if slug in COMPANY_DISPLAY_NAMES:
        return COMPANY_DISPLAY_NAMES[slug]
    if company and company.strip().lower() == (slug or ""):
        # A bare slug (e.g. from history): use the learned display name if known.
        learned = load_registry().get(slug, {}).get("display_name")
        if learned:
            return learned
    return " ".join((company or "").split())


def logo_path(company: str, logos_dir: Path | None = None) -> Path | None:
    """Logo PNG of a company, or None.

    With `logos_dir`, only that directory is searched (tests); otherwise the built-in
    library first, then the learned cache.
    """
    slug = company_slug(company)
    if slug is None:
        return None
    dirs = [logos_dir] if logos_dir is not None else [COMPANY_LOGOS_DIR, learned_logos_dir()]
    for directory in dirs:
        path = directory / f"{slug}.png"
        if path.is_file():
            return path
    return None
