"""Runs one structured LLM call for a given capability tier/role, and records what
was actually used (never invented) as a ModelAssignment."""

from __future__ import annotations

from typing import Type, TypeVar

from langchain.agents import create_agent
from pydantic import BaseModel

from contract_reviewer.config import TierConfig
from contract_reviewer.schemas import ModelAssignment

T = TypeVar("T", bound=BaseModel)


def invoke_structured(
    tier: TierConfig,
    role: str,
    messages: list[dict],
    schema: Type[T],
    tools: list | None = None,
) -> tuple[T, ModelAssignment]:
    """Invoke `role`'s LLM call at `tier`, optionally with tools bound, returning the
    parsed structured response and the real provider/model/tier used for this call."""
    agent = create_agent(
        model=f"{tier.provider}:{tier.model}",
        tools=tools or [],
        response_format=schema,
    )
    result = agent.invoke({"messages": messages})
    structured: T = result["structured_response"]
    assignment = ModelAssignment(
        role=role,
        tier=tier.name,
        provider=tier.provider,
        model=tier.model,
    )
    return structured, assignment
