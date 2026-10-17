"""Sanity tests for FanInGuard environment."""

import importlib.metadata as metadata
import pytest


def test_package_versions():
    """Verify pinned LangGraph and LangChain versions."""
    langgraph_ver = metadata.version("langgraph")
    langchain_core_ver = metadata.version("langchain-core")
    assert langgraph_ver == "1.0.10"
    assert langchain_core_ver == "1.2.17"


def test_import_faningard():
    """Verify faningard package imports cleanly."""
    import faningard
    assert faningard.__version__ == "0.1.0"
