# Technical Comparison: Khan (2026) vs. FanInGuard

**Reference Document:** Sajjad Khan, *"Verified Detection and Prevention of Concurrency Anomalies in Multi-Agent Large Language Model Systems"*, arXiv:2606.17182 [cs.LG], June 15, 2026.

---

## 1. Executive Summary

Khan (2026) introduces a formal verification framework and runtime guards for shared-state multi-agent systems, focusing on data-race and message-ordering consistency anomalies. In contrast, **FanInGuard** is a post-hoc diagnostic and root-cause failure attribution system designed specifically for the LangGraph superstep orchestration engine. It detects and explains **unexpected duplicate node execution at fan-in points** caused by graph topological asymmetry and discrete superstep scheduling.

Crucially, **fan-in duplicate node execution is not part of Khan's anomaly taxonomy**. As a result, Khan (2026) is a foundational conceptual neighbor in LLM concurrency, but cannot serve as an empirical detection baseline.

---

## 2. Khan (2026) Anomaly Taxonomy

Khan formalizes five specific concurrency anomalies arising when multiple autonomous agents read and write to a shared execution workspace:

1. **Stale-Generation Overwrite:** An agent generates a response or state patch based on an outdated view of shared state, overwriting concurrent valid updates from another agent.
2. **Phantom-Tool Invocation:** A tool is invoked by an agent based on a condition that has already been invalidated by a parallel agent's intermediate action.
3. **Causal Cascade Failure:** A desynchronized state update from Agent A triggers an erroneous conditional branch in Agent B, which propagates compounding state corruption.
4. **Tool-Effect Reordering:** The actual side-effects of external tool calls execute in an order divergent from the logical sequence expected by the agent planner.
5. **Split-View Inconsistency:** Two concurrent agents observe mutually conflicting subsets of the global state at the same timestamp.

---

## 3. Dimensional Comparison

| Dimension | Khan (2026) — arXiv:2606.17182 | FanInGuard (Our Work) |
| :--- | :--- | :--- |
| **Primary Target** | Shared-state consistency across autonomous agents | Orchestration engine scheduling anomalies (LangGraph) |
| **Core Phenomenon** | Data races, stale reads, out-of-order writes | Unexpected duplicate execution of fan-in nodes |
| **Underlying Mechanism** | Concurrent uncoordinated agent memory mutations | Pregel discrete supersteps with asymmetric leg lengths |
| **Methodology** | Formal deductive verification (Verus, TLA+) + runtime locks | Static graph topological analysis + dynamic trace ingestion |
| **Intervention Point** | Preventive (blocks invalid state transitions at runtime) | Post-hoc attribution & remediation (explains *why* and fixes edge definitions) |
| **Semantic Judgment** | Verifies formal safety invariants | Rule-based deterministic engine attribution (zero LLM evaluation) |
| **Orchestrator Scope** | Framework-agnostic multi-agent shared-memory systems | LangGraph `StateGraph` workflows (Python and JS) |

---

## 4. Why Khan (2026) is Not a Like-for-Like Baseline

In our empirical evaluation (Phase 9), reviewers may ask whether Khan (2026) should be compared as a baseline detector. The answer is negative for two sound scientific reasons:

1. **Orthogonal Problem Space:** Khan's anomaly set addresses state mutations, not graph control-flow re-activation. A node executing twice without corrupting state keys (or simply appending to a list reducer) is completely invisible to Khan's safety properties.
2. **Implementation Model:** Khan requires specifying formal TLA+ state machine models and instrumenting runtime locks, which prevents application to existing compiled LangGraph traces.

### Positioning in Our Paper (Section 9 — Related Work)
We cite Khan (2026) in Section 9(d) (*Concurrency Anomalies & Formal Verification of Agent Frameworks*) as pioneering work in formal agent state consistency, contrasting our focus on engine-level topology traps and automated post-hoc explanation generation.
