# Engineering & Research Log — FanInGuard

This log tracks all actions, empirical findings, and failures day by day and phase by phase.

---

## 2026-10-17 — Phase 0: Project Inception & Setup

### What was done:
1. **Repository Setup**:
   - Cleaned root repository structure. Connected to GitHub remote `origin/main`.
   - Created Python package structure (`src/faningard`, `docs/`, `tests/`, `benchmark/`, `experiments/`, `paper/`, `results/`, `app/`).
   - Created `pyproject.toml` with pinned dependencies (`langgraph==1.0.10`, `langchain-core==1.2.17`, Python `3.12.5`).
   - Created `FanInGuard_Implementation_Roadmap.md` as the single source of truth.
   - Installed `faningard` in editable mode (`pip install -e .`).
2. **Core Data Models**:
   - Implemented `TraceEvent`, `GraphModel`, and `Finding` dataclasses in `src/faningard/models.py`.
   - Added unit tests in `tests/test_models.py` and sanity tests in `tests/test_sanity.py`. All 5 tests passing.
3. **Execution Environment Verification**:
   - Verified Python: `3.12.5`.
   - Verified LangGraph: `1.0.10`.
   - Verified LangChain Core: `1.2.17`.

### What was found:
- `langgraph` module in 1.0.10 does not expose `__version__` directly on the module top-level; version is retrieved reliably via `importlib.metadata.version('langgraph')`.
- Initial repo had an unintended nested git directory from a clone command; resolved by consolidating files directly into the root workspace folder.

### What failed / Blockers resolved:
- `pytest` was initially missing in the global Python environment. Installed `pytest-9.1.1` and executed successfully via `python -m pytest`.
