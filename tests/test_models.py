"""Tests for FanInGuard core data models."""

from faningard.models import Finding, GraphModel, TraceEvent


def test_trace_event_creation():
    event = TraceEvent(
        event_id="evt_01",
        node="D",
        superstep=2,
        run_id="run_123",
        triggers=["C1"],
        writes={"log": ["D"]},
    )
    assert event.node == "D"
    assert event.superstep == 2
    assert event.triggers == ["C1"]


def test_graph_model_creation():
    model = GraphModel(
        nodes=["A", "B", "C", "D"],
        edges=[("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")],
        join_edges={},
        deferred_nodes=set(),
    )
    assert len(model.nodes) == 4
    assert len(model.edges) == 4


def test_finding_creation():
    finding = Finding(
        rule_id="R1",
        rule_name="DUPLICATE_AT_FANIN",
        node="D",
        supersteps=[2, 3],
        branches=[["A", "C1", "D"], ["A", "B1", "B2", "D"]],
        evidence=["evt_01", "evt_02"],
        explanation="Node D executed 2 times across supersteps 2 and 3.",
        remediation="Use a join edge: add_edge(['B2', 'C1'], 'D').",
    )
    assert finding.rule_id == "R1"
    assert finding.node == "D"
    assert finding.confidence == "HIGH"
