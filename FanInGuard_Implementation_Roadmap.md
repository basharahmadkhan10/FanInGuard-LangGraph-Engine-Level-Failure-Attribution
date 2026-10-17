# FanInGuard — Implementation & Publication Roadmap
**Project:** LangGraph Engine-Level Failure Attribution — Unexpected Duplicate Node Execution at Fan-In
**Working tool name:** FanInGuard (rename freely)
**Purpose of this file:** Single source of truth for an AI coding/research agent (Antigravity) and the student team. Follow it phase by phase. Do not skip acceptance criteria.

---

## 0. Instructions to the Agent (READ FIRST)

You are acting as a research engineer and co-author. Your goal: build a working, validated prototype AND produce the evidence needed for a publishable paper.

**Non-negotiable rules**
1. **Never fabricate** citations, issue contents, benchmark numbers, or experimental results. Every number in the paper must come from a script in this repo that can be re-run.
2. **Verify every reference** against its real source (arXiv/DOI/publisher page/GitHub URL) before adding it to `paper/references.bib`. If you cannot verify it, do not cite it. (The earlier draft review had in-text citations mapped to wrong reference entries; this must not repeat.)
3. **Read the real GitHub issues** yourself and write what each actually reports: langchain-ai/langgraph #7727, #4026, #3617; langchain-ai/langgraphjs #1535, #2666. Prior team check (re-verify and record dates/status yourself): #4026, #7727 (Python) and #1535 (JS) report a fan-in node running more times than expected; #2666 (JS) reports a join node silently never running when a parent is conditionally skipped and tabulates three fan-in wirings; **#3617 is NOT a duplicate-execution issue** (it reports nodes in one parallel branch seeing the other branch's state updates at superstep boundaries), so classify it as adjacent/shared-state, not as evidence of duplicates. Some reports may be "expected behavior" rather than bugs; report that honestly.
4. **Pin versions.** LangGraph behavior can change across releases. Record exact versions (`langgraph`, `langchain-core`, Python) in every experiment output.
5. **Ask before assuming** when a requirement is ambiguous. Otherwise proceed.
6. **Commit after every task** with a clear message. Keep a `docs/LOG.md` with date, what was done, what was found, what failed.
7. Each phase ends with: deliverables present, tests passing, `docs/LOG.md` updated.

**Suggested kickoff prompt to paste into Antigravity**
> Read `FanInGuard_Implementation_Roadmap.md` fully. Start at Phase 0. Create the repo structure from Section 5, then execute phases in order. After each phase, summarize deliverables, test results, and open questions, then wait for my confirmation before the next phase.

---

## 1. Problem Statement and Thesis

**Problem.** In LangGraph, a node downstream of parallel branches can execute more times than the developer intended. Cause: LangGraph runs in discrete *supersteps*. If separate edges lead from different branches into the same node and the branches finish in different supersteps, the target node is activated in each of those supersteps and runs multiple times. Consequences: duplicated outputs, extra LLM/tool calls, extra cost and latency, inconsistent state.

**Why it is hard to debug.** Traces (LangSmith, LangGraph Studio) show *what ran*, but the developer must manually infer *why* a node ran twice (which branches, which superstep, which edge definition).

**Thesis (one sentence).** A deterministic, rule-based analyzer that combines static graph structure with an actual execution trace can automatically detect and explain unexpected duplicate execution at fan-in points in LangGraph, with high precision, and without judging LLM reasoning.

**Contributions to claim (only if evidence supports them)**
- C1. A precise taxonomy/formalization of fan-in duplicate execution in LangGraph's superstep model.
- C2. A static + dynamic rule-based detector with human-readable root-cause explanations (node, superstep, contributing branches, offending edge definition, suggested fix).
- C3. An open benchmark of LangGraph workflows (buggy, correct, and "legitimate duplicate" cases) with ground-truth labels.
- C4. Empirical evaluation: precision/recall/F1, explanation correctness, overhead, and comparison with baselines.
- C5. (Optional) Version-sensitivity study across LangGraph releases.

## 2. Scope and Non-Goals

**In scope:** Python LangGraph `StateGraph` workflows; fan-in duplicate execution; post-hoc analysis of one run's trace; static risk warnings from graph structure alone.
**Out of scope:** judging LLM answer quality; detecting all agent failures; replacing LangSmith/Studio; formal proofs of correctness; LangGraphJS implementation (mention as future work; cite issues #1535 and #2666 only as evidence the pattern exists across ports).

## 3. Technical Background the Agent Must Understand

- **Superstep (Pregel-style) model:** nodes activate when they receive messages; all active nodes in a superstep run in parallel; their writes are applied at superstep end; the next superstep begins.
- **Separate edges into one node:** `add_edge("B","D")` and `add_edge("C","D")` as two calls means D is triggered by each independently.
- **Join edge:** `add_edge(["B","C"],"D")` means D waits until *all* listed sources have completed. Reported caveat (#2666): if one source never runs (e.g., it sits behind a conditional edge that does not select it), D and everything after it silently never run while the call still returns normally. Verify empirically in Python.
- **Deferred nodes:** `add_node("D", fn, defer=True)` delays D until the rest of the pending work finishes (verify exact semantics in the installed version's docs). Reported caveat (#2666, with a commenter reporting the same on Python 1.2.11): defer waits for all pending work in the graph, not only D's ancestors, so an unrelated slow branch delays D. Treat "defer fixes duplicates" as a hypothesis to test, not a fact.
- **Intentional repeated execution (must NOT be flagged):** loops/cycles, `Send` API map-reduce (same node runs once per item), retries, human-in-the-loop resumes (a node re-runs from its beginning after `interrupt()` is resumed; practitioners describe this as by design), and subgraph-internal scheduling (a subgraph runs its own supersteps, so a fan-in inside it is judged separately from the parent graph).
- **Reducers:** concurrent writes to the same state key need a reducer (e.g., `Annotated[list, operator.add]`) or LangGraph raises an invalid concurrent update error. Duplicate execution plus an appending reducer produces duplicated state entries.

> Task for agent: write `docs/BACKGROUND.md` summarizing the above **from the official LangGraph docs of the pinned version**, with links. Empirically confirm each claim with a tiny script (Phase 1).

## 4. Formal Definitions (draft; refine in Phase 2)

Let G = (V, E) be the compiled graph. Let a *run* produce a trace T = sequence of task events (node, superstep, run_id, triggers, timestamps).

- **exec(n, T):** number of times node n executed in T (per invocation, excluding intentional repeats).
- **Fan-out ancestor:** node a with ≥2 outgoing edges whose branches reconverge.
- **Fan-in node:** node n with ≥2 distinct predecessor sets reachable from a common fan-out ancestor.
- **Join-protected fan-in:** all incoming parallel edges are expressed as one join edge, or n is deferred.
- **Predicted activation set A(n):** set of supersteps in which n is expected to be activated, computed from path lengths for acyclic, unconditional regions. For regions with conditional edges, cycles, or `Send`, A(n) is *indeterminate* and only dynamic rules apply.
- **Developer intent I(n):** whether n is meant to run once per invocation. Source of truth: (a) explicit annotation (e.g., `expected_runs={"D":1}` passed to the tool) or (b) heuristic default: a fan-in node reconverging parallel branches from one ancestor is intended once. **State this heuristic as a threat to validity in the paper.**

**Rules (deterministic)**
- **R1 (dynamic, core):** n is a fan-in node, I(n)=once, exec(n,T) > 1, and the executions occur in distinct supersteps triggered by different predecessors → report DUPLICATE_AT_FANIN.
- **R2 (static risk):** n is a fan-in node with separate incoming edges from branches of unequal path length and no join edge/defer → report RISK_UNEQUAL_LEGS (before running anything).
- **R3 (dynamic, secondary anomaly class):** n is the target of a join edge, at least one but not all of its join sources executed, and the run ended without n executing (e.g., a source sat behind a conditional edge that did not select it) → report JOIN_NEVER_FIRED (silent partial execution; see #2666). Evidence comes from the executed-node set in the trace; if the installed version exposes pending join-barrier state in checkpoints (reported in #2666), use it as corroboration after verifying it. This is not a duplicate-execution anomaly: keep it clearly labelled as a second, smaller contribution.
- **R4 (dynamic, side effect):** duplicate execution of n coincides with duplicate entries in a reducer-managed state key → report DUPLICATE_STATE_EFFECT.
- **Suppressions:** do not fire R1 when n is inside a cycle, is a `Send` target, is the re-run of an interrupted node after resume, is inside a subgraph being analyzed against the parent graph, or has I(n)=many.

Each finding must carry: rule id, node, supersteps, predecessor branches, evidence (trace event ids), explanation text, suggested remediation, confidence = HIGH for deterministic rule matches (no probabilistic scoring needed).

## 5. Repository Structure

```
faningard/
├── README.md
├── pyproject.toml            # pinned deps, python>=3.11
├── docs/
│   ├── LOG.md
│   ├── BACKGROUND.md
│   ├── ISSUE_ANALYSIS.md     # real summaries of GitHub issues
│   ├── RULES_SPEC.md         # formal rule definitions
│   └── THREATS_TO_VALIDITY.md
├── src/faningard/
│   ├── models.py             # Finding, TraceEvent, GraphModel dataclasses
│   ├── graph_extract.py      # compiled graph -> GraphModel
│   ├── trace_ingest.py       # stream debug / checkpoints / LangSmith export -> TraceEvent list
│   ├── static_analysis.py    # fan-in detection, path lengths, A(n), R2
│   ├── dynamic_rules.py      # R1, R3, R4, suppressions
│   ├── explain.py            # natural-language explanations + fix suggestions
│   ├── report.py             # JSON / Markdown / HTML report, graph highlight
│   ├── instrument.py         # optional node wrapper for execution counting
│   └── cli.py
├── app/streamlit_app.py      # demo UI
├── benchmark/
│   ├── graphs/               # one file per workflow
│   ├── labels.yaml           # ground truth per workflow
│   ├── generator.py          # synthetic graph generator + mutations
│   └── run_benchmark.py
├── experiments/              # scripts producing every number/table/figure in paper
├── tests/
├── paper/
│   ├── main.tex (or .md)
│   ├── references.bib
│   └── figures/
└── results/                  # raw outputs (csv/json), versioned with langgraph version tag
```

---

## 6. Phased Roadmap

### Phase 0 — Setup and Evidence Gathering (Week 1)
**Tasks**
1. Create repo, virtualenv, pin `langgraph` and `langchain-core`. Add CI (lint + tests).
2. Read the GitHub issues (#7727, #4026, #3617 in langgraph; #1535, #2666 in langgraphjs; also #6005 in langgraph, which #2666 cites for the maintainer explanation of edges and defer). Write `docs/ISSUE_ANALYSIS.md`: for each issue give title, date, what is reported, minimal reproduction if given, maintainer response, whether it is a bug, a documented behavior, or a question. Mark #3617 as adjacent (shared-state visibility), not a duplicate-execution case, unless your own reading shows otherwise.
3. Read Khan (2026), arXiv:2606.17182 (independent-researcher preprint). Prior team check: it formalizes stale-generation, phantom-tool, causal-cascade, and tool-effect reordering (plus split-view) for shared-state multi-agent runtimes, and fan-in duplicate execution is not among them. Confirm this yourself and write a 1-page comparison (what it detects/prevents, formal verification vs. our post-hoc approach).
4. Collect 15–25 *verified* related papers/docs across: LangGraph/Pregel execution semantics; agent failure attribution; observability/provenance/tracing (OpenTelemetry GenAI conventions, LangSmith); workflow/Petri-net/BPM correctness; concurrency bug detection. Store with verified BibTeX.
**Deliverables:** repo, `ISSUE_ANALYSIS.md`, `related_work_table.csv` (paper, venue, year, relevance, what it does, how we differ), `references.bib`.
**Acceptance:** every bib entry has a working URL/DOI; every issue is summarized from the actual page.

### Phase 1 — Reproduce and Characterize the Behavior (Week 2)
**Tasks**
1. Implement minimal reproducible graphs in `benchmark/graphs/`:
   - `fanin_unequal_legs_buggy`: START→A; A→B1→B2→D; A→C1→D with *separate* edges (expected: D activated in two supersteps).
   - `fanin_unequal_legs_join_fixed`: same, with `add_edge(["B2","C1"],"D")`.
   - `fanin_equal_legs_separate_edges`: equal path lengths (expected: single activation).
   - `fanin_deferred`: using `defer=True`.
   - `fanin_conditional_branches`: conditional edges converging.
   - Legit negatives: `loop_graph`, `send_mapreduce`, `retry_graph`, `interrupt_resume_rerun`, `subgraph_branch` (a branch wrapped in a subgraph; reported to run the target once).
   - Edge cases from the issue reports: `fanin_conditional_skipped_join` (join edge with a conditionally skipped parent; expect target never runs), `fanin_defer_unrelated_slow_branch` (does defer wait for unrelated work?), `fanin_static_plus_send` (static edges mixed with `Send` fan-out), `fanin_plain_plus_conditional_edge` (plain and conditional edge to the same target).
2. For each, run and record: per-node execution counts, superstep numbers, state outputs. Save as raw JSON.
3. Confirm or refute each expectation empirically. If a prediction is wrong, **update the formal model**, not the data.
4. Repeat on at least 3 LangGraph versions (oldest supported you can install, a mid version, latest) to measure version sensitivity. Include versions named in the issue reports (Python 1.1.10 in #7727, 1.2.11 in a #2666 comment) so results can be compared with what reporters observed.
**Deliverables:** `results/phase1_*.json`, a table "graph × version → exec counts".
**Acceptance:** the duplicate-execution behavior is reproduced deterministically (≥20 repeated runs identical), and documented.

### Phase 2 — Taxonomy and Rule Specification (Week 3)
**Tasks**
1. Write `docs/RULES_SPEC.md` with the definitions in Section 4, refined using Phase 1 findings. Include a taxonomy figure: causes of duplicate execution (unequal legs, separate edges, conditional convergence, shared-state re-trigger, etc.) vs. intended repeats.
2. Specify exact inputs/outputs for each rule and the suppression logic.
3. Write unit-test stubs for each rule (positive, negative, edge cases).
**Deliverables:** `RULES_SPEC.md`, taxonomy figure, test stubs.
**Acceptance:** a second person (or reviewer agent) can implement R1 from the spec alone and get identical results on Phase 1 graphs.

### Phase 3 — Graph Extraction and Trace Ingestion (Weeks 4)
**Tasks**
1. `graph_extract.py`: from `compiled.get_graph()` (nodes, edges, conditional flags) build `GraphModel`. Detect join edges and deferred nodes if exposed; if not exposed by the API, add a documented fallback (e.g., read builder metadata or accept a lightweight user-provided annotation) and record this as a limitation.
2. `trace_ingest.py`: support at least two sources:
   - (a) `stream_mode="debug"` events (task start/result with step numbers),
   - (b) checkpoint history (`get_state_history`, using step metadata).
   - (c) *Stretch:* LangSmith run export (JSON) to show real-world applicability.
   Normalize to `TraceEvent(node, superstep, run_id, triggers, started_at, ended_at)`. Verify the exact event schema in the installed version; do not assume.
3. `instrument.py`: optional wrapper to count executions as an independent ground-truth oracle used only in evaluation.
**Deliverables:** extractors + ingestors with tests.
**Acceptance:** on all Phase 1 graphs, ingested supersteps match manual inspection; oracle counts equal ingested counts.

### Phase 4 — Static Analyzer (Week 5)
**Tasks**
1. Detect fan-out ancestors and fan-in nodes.
2. Compute path lengths and predicted activation sets A(n) for acyclic/unconditional regions; mark others indeterminate.
3. Implement R2 (RISK_UNEQUAL_LEGS) with remediation hints.
4. Validate predictions against Phase 1 observed supersteps: report prediction accuracy.
**Deliverables:** `static_analysis.py`, tests, accuracy table.
**Acceptance:** A(n) matches observed activation supersteps on all determinate graphs; indeterminate cases are labeled, never guessed.

### Phase 5 — Dynamic Detector (Weeks 6–7)
**Tasks**
1. Implement R1, R3, R4 and suppressions (cycles, `Send`, retries, I(n)=many).
2. Support user annotation of intent (`expected_runs`), with the documented default heuristic.
3. Produce structured `Finding` objects with evidence event ids.
4. Property-based tests (Hypothesis) on generated graphs: detector never flags join-protected equal-leg graphs; always flags known buggy templates.
**Deliverables:** `dynamic_rules.py`, test suite ≥ 90% coverage on rules.
**Acceptance:** zero false positives on legit-duplicate negatives; zero false negatives on Phase 1 buggy graphs.

### Phase 6 — Explanation and Remediation Engine (Week 8)
**Tasks**
1. Template-based (deterministic, no LLM) explanations, e.g.:
   > "Node D executed 2 times (supersteps 3 and 4). Branch A→C1 reached D at superstep 2; branch A→B1→B2 reached D at superstep 3. D is connected by separate edges, so it is triggered once per arriving branch. Fix: replace `add_edge('B2','D')` and `add_edge('C1','D')` with `add_edge(['B2','C1'],'D')`, or mark D `defer=True`."
2. Attach evidence list (event ids) and static-analysis cross-reference (R2 predicted this before the run).
3. Render graph with the offending node/edges highlighted.
**Deliverables:** `explain.py`, `report.py` (JSON, Markdown, HTML).
**Acceptance:** explanation names the correct node, supersteps, and branches on 100% of detected benchmark cases (checked automatically against labels).

### Phase 7 — CLI and Demo UI (Week 9)
**Tasks**
1. CLI: `faningard analyze --graph module:app --trace trace.json --expect D=1`.
2. Streamlit app: upload/select graph + trace, view findings, highlighted graph, superstep timeline.
3. One-command demo script that runs buggy → shows finding → applies suggested fix → shows clean result (the "before/after" demo for the capstone viva).
4. README with quickstart, screenshots, limitations.
**Deliverables:** working demo, README, 2-minute screen recording script.
**Acceptance:** a fresh machine can install and reproduce the demo in <10 minutes following README only.

### Phase 8 — Benchmark Construction (Weeks 9–10, parallel with Phase 7)
**Design** (target ≥ 100 workflows; state exact counts in paper)
| Category | Description | Label | Min count |
|---|---|---|---|
| A | Buggy fan-in: separate edges, unequal legs | duplicate | 25 |
| B | Buggy fan-in: conditional convergence | duplicate | 15 |
| C | Correct: join edge / defer | no issue | 25 |
| D | Correct: equal legs | no issue | 15 |
| E | Legit repeats: loops, `Send` map-reduce, retries, resume, subgraph | no issue (tests suppression) | 25 |
| F | Real-world-style: workflows adapted from public LangGraph tutorials/examples/issues (cite sources and licenses) | mixed | 10+ |
| G | Join/defer edge cases: conditionally skipped join, defer with unrelated slow branch (labels from your own empirical runs) | mixed (R3 and R1 negatives) | 10 |

**Tasks**
1. Hand-write seed graphs (include graphs derived from the GitHub issues).
2. `generator.py`: random DAG generator (parameters: depth, width, leg-length variance, edge style) and **mutation operators** (split join into separate edges, lengthen a leg, remove defer, add conditional edge).
3. Ground truth = (a) design intent label + (b) independent oracle from `instrument.py` execution counts. Resolve disagreements manually and document each.
4. Add dummy deterministic node bodies (no real LLM calls) so runs are free and reproducible; add a smaller set with real LLM-calling nodes to show cost impact (optional, small).
**Deliverables:** `benchmark/` + `labels.yaml` + datasheet (how built, biases, license).
**Acceptance:** benchmark runs end-to-end with one command; labels reviewed by at least two people.

### Phase 9 — Evaluation (Weeks 10–11)
**Research questions**
- RQ1: How accurately does FanInGuard detect fan-in duplicate execution? (precision, recall, F1 overall and per category)
- RQ2: Are its explanations correct and complete? (node, superstep, branches, edge cause — automatic check vs. labels)
- RQ3: Does it avoid flagging intentional repeats? (false-positive rate on category E)
- RQ4: What is the overhead? (analysis time vs. graph size/trace length; runtime overhead of debug streaming)
- RQ5: Does it help developers vs. manual trace inspection? (small user study)
- RQ6 (optional): How does behavior/detection vary across LangGraph versions?

**Baselines**
- B1: Naive counter (flag any node with exec > 1).
- B2: Manual inspection via LangSmith/Studio (user study, see below).
- B3: (Optional) LLM-as-judge prompted with trace text, run ≥3 times to show non-determinism and cost. Report honestly even if it performs well.
- B4: Khan (2026): its anomaly set does not include fan-in duplicates, so it is not a like-for-like baseline; discuss qualitatively in related work instead of reporting numbers.

**Ablations:** static-only vs. dynamic-only vs. combined; with/without suppressions; with/without intent annotation (heuristic default only).

**User study (small, honest):** ≥ 8 participants (classmates/seniors with LangGraph or Python experience). Task: find why a node ran twice in 4 graphs, with vs. without tool (counterbalanced). Measure time-to-diagnosis and correctness. Obtain consent, anonymize, report as a *preliminary* study with limitations. If ethics approval is required by the institution, obtain it first.

**Statistics:** report confidence intervals (bootstrap) for precision/recall; paired tests for the user study (e.g., Wilcoxon signed-rank); state sample sizes. No cherry-picking: report failures and misses.

**Deliverables:** `experiments/*.py`, `results/*.csv`, final tables/figures auto-generated by script `make_figures.py`.
**Acceptance:** `make all` regenerates every table and figure in the paper from raw results.

### Phase 10 — Paper Writing (Weeks 11–12)
**Target format:** 8–10 pages (IEEE/ACM two-column; match the target venue's template exactly). Also post to arXiv.

**Outline**
1. **Abstract** (150–200 words): problem, gap, approach, benchmark, headline numbers (only real ones), availability.
2. **Introduction:** motivating example (the 5-node graph), real-world evidence (GitHub issues, as summarized in ISSUE_ANALYSIS), contributions list, paper roadmap.
3. **Background:** LangGraph supersteps, join edges, deferred nodes, observability tools.
4. **Problem Formalization:** definitions and taxonomy (Section 4 of this roadmap).
5. **Approach (FanInGuard):** architecture figure, static analysis, dynamic rules, suppressions, explanation generation.
6. **Benchmark:** construction, categories, ground truth, datasheet.
7. **Evaluation:** RQ1–RQ6, baselines, ablations, user study, results.
8. **Discussion:** why rule-based, when it fails, how to integrate with LangSmith/CI, **threats to validity** (intent heuristic, benchmark synthetic bias, version drift, small user study).
9. **Related Work:** (a) LangGraph/agent orchestration semantics, (b) agent failure attribution (e.g., which agent/step failed — contrast: we analyze engine behavior, not reasoning), (c) observability/provenance/tracing, (d) concurrency anomalies and formal verification of agent frameworks (incl. Khan 2026 — contrast: formal/prevention vs. post-hoc detection on real traces), (e) workflow correctness (control-flow/soundness analysis).
10. **Conclusion and Future Work:** runtime prevention, JS port, additional engine anomalies (lost updates, join never fired, state races), IDE/CI plug-in.
11. **Artifact Availability:** repo URL, archived DOI (Zenodo), versions.

**Writing rules:** claims must map to a table/figure; define "unexpected" precisely; avoid words like "novel" unless the related-work table backs it; every limitation stated; no unverifiable statements.

**Required figures/tables:** F1 motivating graph + superstep timeline; F2 architecture; F3 taxonomy; T1 related-work comparison; T2 benchmark composition; T3 main results (P/R/F1 by category and baseline); T4 explanation correctness; T5 overhead; T6 user study; T7 ablations; T8 cross-version results.

### Phase 11 — Artifact Packaging and Reproducibility (Week 12)
1. Clean README, license (MIT/Apache-2.0), `CITATION.cff`, CONTRIBUTING.
2. Dockerfile or lockfile; one-command reproduction (`make all`).
3. Release v1.0, archive on Zenodo to get a DOI; cite it in the paper.
4. Optional: publish to PyPI as `faningard`.
5. Reproducibility checklist (versions, seeds, hardware, runtimes).

### Phase 12 — Submission (after Week 12)
1. **Pre-submission review:** internal read by 2 people who did not write it; fix every confusion. Run a grammar/plagiarism check; ensure paraphrasing and proper attribution.
2. **Venue selection (check current deadlines and scope yourself):** prefer (a) workshops or tracks on software engineering for AI/LLM agents, AI observability, or reliability; (b) tool/demo tracks, since the contribution is a tool plus benchmark; (c) reputable regional/IEEE/ACM-indexed conferences if timing is tight; (d) a journal later with extended evaluation. Avoid predatory venues: verify indexing, program committee, past proceedings.
3. Post preprint to arXiv (check the venue's policy on preprints first).
4. Prepare rebuttal material: threats to validity, extra experiments ready.
5. Faculty mentor review and authorship agreement (contribution list) before submission.

---

## 7. Timeline Summary (12 weeks; compress or stretch to the capstone calendar)

| Week | Phase | Milestone |
|---|---|---|
| 1 | 0 | Issues + related work verified |
| 2 | 1 | Behavior reproduced across versions |
| 3 | 2 | Rules spec frozen |
| 4 | 3 | Extraction + ingestion working |
| 5 | 4 | Static analyzer + R2 |
| 6–7 | 5 | Dynamic detector, suppressions |
| 8 | 6 | Explanations + report |
| 9 | 7, 8 | CLI/UI demo; benchmark build starts |
| 10–11 | 8, 9 | Benchmark complete; experiments + user study |
| 11–12 | 10 | Paper draft |
| 12 | 11 | Artifact release |
| 12+ | 12 | Submission |

**Capstone demo checkpoint (earliest safe demo):** end of Week 7 (static + dynamic detection with before/after fix on Phase 1 graphs).

## 8. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Behavior differs across LangGraph versions or has been fixed upstream | Version-sensitivity study (RQ6); frame as "engine semantics trap" + detection, not "bug" |
| Trace API doesn't expose join/defer info | Fallback annotations; document limitation; test multiple ingestion sources |
| Reviewers say "this is documented behavior, trivial" | Position contribution as automated attribution + benchmark + evaluation, show manual-diagnosis difficulty in user study |
| Synthetic benchmark criticized as unrealistic | Include category F real-world-style graphs; release datasheet; discuss threats |
| False positives on intentional repeats | Suppression rules + dedicated negative category E + ablation |
| Too small a user study | Present as preliminary; report CIs; promise larger study as future work |
| Scope creep | Anything beyond fan-in duplicate execution goes to "Future Work" |

## 9. Ethics, Integrity, and Credit
- Cite all sources; paraphrase, do not copy text from blogs, docs, or papers.
- Respect licenses for any graphs adapted from public repos.
- User study: informed consent, anonymized data, institutional approval if required.
- Do not overclaim: no "first" or "novel" without literature evidence; no generalization beyond tested LangGraph versions.
- AI-assistance disclosure: follow the target venue's policy on AI tool usage in writing and coding.

## 10. Definition of Done (checklist)
- [ ] All referenced GitHub issues (#7727, #4026, #3617, #1535, #2666) read and summarized accurately, with #3617 classified correctly
- [ ] Every reference verified; in-text citations match the bibliography
- [ ] Duplicate-execution behavior reproduced on ≥3 LangGraph versions
- [ ] Rules R1–R4 + suppressions implemented and unit-tested
- [ ] Benchmark ≥100 workflows with reviewed ground truth
- [ ] Precision/recall/F1, explanation correctness, overhead measured with CIs
- [ ] Baselines and ablations reported honestly, including failures
- [ ] User study completed and analyzed
- [ ] Demo works from a clean machine in <10 minutes
- [ ] `make all` regenerates every number, table, and figure
- [ ] Paper follows target venue template; limitations and threats to validity included
- [ ] Artifact released with DOI; README and license present
- [ ] Mentor review done; submission package ready
