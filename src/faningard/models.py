"""Core data models for FanInGuard.

Defines schemas for trace events, graph representation, and rule attribution findings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TraceEvent:
    """Represents a discrete node execution event in a LangGraph superstep trace."""

    event_id: str
    node: str
    superstep: int
    run_id: str
    triggers: list[str] = field(default_factory=list)
    started_at: float | None = None
    ended_at: float | None = None
    writes: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphModel:
    """Normalized structural representation of a compiled LangGraph workflow."""

    nodes: list[str] = field(default_factory=list)
    edges: list[tuple[str, str]] = field(default_factory=list)
    join_edges: dict[str, list[str]] = field(default_factory=dict)  # target -> list of sources
    deferred_nodes: set[str] = field(default_factory=set)
    conditional_edges: list[tuple[str, list[str]]] = field(default_factory=list)  # source -> list of targets


@dataclass
class Finding:
    """An engine-level failure attribution finding emitted by FanInGuard."""

    rule_id: str  # R1, R2, R3, R4
    rule_name: str  # DUPLICATE_AT_FANIN, RISK_UNEQUAL_LEGS, JOIN_NEVER_FIRED, etc.
    node: str
    supersteps: list[int]
    branches: list[list[str]]  # predecessor paths that triggered each execution
    evidence: list[str]  # TraceEvent event_ids
    explanation: str
    remediation: str
    static_prediction: bool = False  # True if predicted by R2 statically
    confidence: str = "HIGH"
