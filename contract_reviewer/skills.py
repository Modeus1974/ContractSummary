"""Loads Workflow/SKILL.md and Contract Skills/*.md verbatim, with content hashes.

These files are the actual substantive instructions the reviewer/verifier must follow.
This module only reads and caches them as text -- nothing here re-implements their content.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from contract_reviewer.config import PROJECT_ROOT

CONTRACT_SKILLS_DIR = PROJECT_ROOT / "Contract Skills"
WORKFLOW_SKILL_PATH = PROJECT_ROOT / "Workflow" / "SKILL.md"

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass(frozen=True)
class SkillFile:
    relative_path: str
    name: str
    description: str
    kind: str  # "contract-type" (routes the risk-review classifier) or "task" (a different job entirely)
    text: str  # full file content, including frontmatter
    sha256: str


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_frontmatter(text: str) -> dict:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}
    return yaml.safe_load(match.group(1)) or {}


def _load_skill_file(path: Path) -> SkillFile:
    text = path.read_text(encoding="utf-8")
    frontmatter = _parse_frontmatter(text)
    return SkillFile(
        relative_path=str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
        name=frontmatter.get("name", path.stem),
        description=frontmatter.get("description", ""),
        kind=frontmatter.get("kind", "contract-type"),
        text=text,
        sha256=_sha256(text),
    )


@lru_cache(maxsize=1)
def load_contract_skills() -> tuple[SkillFile, ...]:
    return tuple(_load_skill_file(p) for p in sorted(CONTRACT_SKILLS_DIR.glob("*.md")))


def load_routing_skills() -> tuple[SkillFile, ...]:
    """Contract-type skills only (kind: contract-type) -- what the risk-review classifier
    chooses between. Task-type skills (e.g. Contract Summary.md) select a different job
    entirely and must never be offered to that classifier, even though they're still
    loaded/resolvable via load_contract_skills()/skills_by_relative_path() for other uses."""
    return tuple(s for s in load_contract_skills() if s.kind == "contract-type")


@lru_cache(maxsize=1)
def load_workflow_skill() -> SkillFile:
    return _load_skill_file(WORKFLOW_SKILL_PATH)


def all_skill_hashes() -> dict[str, str]:
    hashes = {s.relative_path: s.sha256 for s in load_contract_skills()}
    workflow = load_workflow_skill()
    hashes[workflow.relative_path] = workflow.sha256
    return hashes


def skills_by_relative_path(paths: list[str]) -> dict[str, str]:
    """Resolve selected skill relative paths (from a RoutingRecord) to their full verbatim text."""
    lookup = {s.relative_path: s.text for s in load_contract_skills()}
    resolved: dict[str, str] = {}
    for raw_path in paths:
        normalized = raw_path.replace("\\", "/")
        if normalized in lookup:
            resolved[normalized] = lookup[normalized]
    return resolved
