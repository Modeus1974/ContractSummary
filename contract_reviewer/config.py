"""Loads .env and models.yaml, resolves the Efficient/Balanced/Flagship tiers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent

RELEVANT_ENV_KEYS = (
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "TAVILY_API_KEY",
)


@dataclass(frozen=True)
class TierConfig:
    name: str
    provider: str
    model: str


def load_env() -> None:
    load_dotenv(PROJECT_ROOT / ".env")


def available_providers() -> dict[str, bool]:
    return {key: bool(os.environ.get(key)) for key in RELEVANT_ENV_KEYS}


def load_tier_config(models_config_path: Path | None = None) -> dict[str, TierConfig]:
    """Resolve tier -> (provider, model), applying MODEL_TIER_<TIER>_{PROVIDER,MODEL} env overrides."""
    path = models_config_path or (PROJECT_ROOT / "models.yaml")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    tiers: dict[str, TierConfig] = {}
    for tier_name, tier_data in (raw.get("tiers") or {}).items():
        provider = os.environ.get(
            f"MODEL_TIER_{tier_name.upper()}_PROVIDER", tier_data["provider"]
        )
        model = os.environ.get(
            f"MODEL_TIER_{tier_name.upper()}_MODEL", tier_data["model"]
        )
        tiers[tier_name] = TierConfig(name=tier_name, provider=provider, model=model)

    for required in ("efficient", "balanced", "flagship"):
        if required not in tiers:
            raise ValueError(f"models.yaml is missing required tier '{required}'")
    return tiers
