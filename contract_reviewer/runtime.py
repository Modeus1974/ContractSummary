"""Process-wide resolved tier config, set once by the CLI at startup and read by nodes."""

from __future__ import annotations

from contract_reviewer.config import TierConfig

_tiers: dict[str, TierConfig] | None = None


def set_tiers(tiers: dict[str, TierConfig]) -> None:
    global _tiers
    _tiers = tiers


def get_tiers() -> dict[str, TierConfig]:
    if _tiers is None:
        raise RuntimeError(
            "Tier config not initialized; call runtime.set_tiers() before running the graph"
        )
    return _tiers
