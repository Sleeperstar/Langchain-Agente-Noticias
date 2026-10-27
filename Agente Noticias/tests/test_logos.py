"""Company normalization (any company, key-company aliases) and the evaluator schema."""
from __future__ import annotations

import json

import pytest

from agente_noticias import logos
from agente_noticias.logos import canonical_company, company_slug, display_name, is_key_company
from agente_noticias.schemas import ArticleEvaluation


@pytest.mark.parametrize(
    ("raw", "slug"),
    [
        ("OpenAI", "openai"),
        ("openai", "openai"),
        ("Google DeepMind", "google"),
        ("DeepMind", "google"),
        ("Gemini", "gemini"),
        ("Meta AI", "meta"),
        ("Meta Platforms, Inc.", "meta"),
        ("AWS", "amazon"),
        ("Amazon Web Services", "amazon"),
        ("Alibaba Cloud", "alibaba"),
        ("Qwen", "qwen"),
        ("Mistral AI", "mistral"),
        ("xAI", "xai"),
        ("NVIDIA Corporation", "nvidia"),
    ],
)
def test_company_slug_maps_aliases_to_key_companies(raw, slug):
    assert company_slug(raw) == slug
    assert is_key_company(raw)


@pytest.mark.parametrize(
    ("raw", "slug"),
    [
        ("Walmart", "walmart"),
        ("Walmart Inc.", "walmart"),
        ("1Password", "1password"),
        ("Hugging Face", "hugging-face"),
        ("Société Générale S.A.", "societe-generale"),
    ],
)
def test_company_slug_of_unknown_companies(raw, slug):
    assert company_slug(raw) == slug
    assert not is_key_company(raw)


@pytest.mark.parametrize("raw", [None, "", "   ", "!!!"])
def test_blank_company_has_no_slug(raw):
    assert company_slug(raw) is None
    assert canonical_company(raw) is None


def test_canonical_company_is_idempotent_and_keeps_unknown_names():
    assert canonical_company("Google DeepMind") == "google"
    assert canonical_company("google") == "google"
    assert canonical_company("  1Password  ") == "1Password"
    assert canonical_company(canonical_company("Walmart")) == "Walmart"


def test_display_name_for_keys_names_and_learned_slugs(tmp_path, monkeypatch):
    monkeypatch.setattr(logos, "LEARNED_LOGOS_DIR", tmp_path)
    assert display_name("openai") == "OpenAI"
    assert display_name("Walmart") == "Walmart"
    logos.update_registry("1password", {"status": "found", "display_name": "1Password"})
    assert display_name("1password") == "1Password"  # bare slug from history


def test_logo_path_prefers_builtin_then_learned(tmp_path, monkeypatch):
    monkeypatch.setattr(logos, "LEARNED_LOGOS_DIR", tmp_path)
    assert logos.logo_path("OpenAI").parent == logos.COMPANY_LOGOS_DIR
    assert logos.logo_path("Walmart") is None
    (tmp_path / "walmart.png").write_bytes(b"png")
    assert logos.logo_path("Walmart Inc.") == tmp_path / "walmart.png"


def test_evaluation_accepts_any_company_and_canonicalizes_keys():
    base = dict(
        reasoning="r", relevance_score=7, category="Industria",
        label_es="Negocios", title_es="t", summary_es="s",
    )
    assert ArticleEvaluation(**base, company="Walmart").company == "Walmart"
    assert ArticleEvaluation(**base, company="Google DeepMind").company == "google"
    assert ArticleEvaluation(**base, company=None).company is None
    assert ArticleEvaluation(**base, company=" ").company is None


def test_evaluation_schema_is_openai_strict_with_free_company():
    from openai.lib._parsing._completions import type_to_response_format_param

    fmt = type_to_response_format_param(ArticleEvaluation)
    schema = fmt["json_schema"]["schema"]

    assert fmt["json_schema"]["strict"] is True
    assert set(schema["required"]) == set(schema["properties"])  # strict: all required
    company = json.dumps(schema["properties"]["company"])
    assert '"null"' in company and '"string"' in company
    assert "enum" not in company
