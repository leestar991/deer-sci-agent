"""Tests for subagent session memory (per-thread per-subagent context accumulation)."""

import json
import os
import tempfile
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def temp_base_dir(tmp_path, monkeypatch):
    """Patch the paths module to use a tmp directory as base_dir."""
    from deerflow.config.paths import Paths

    paths = Paths(base_dir=tmp_path)
    monkeypatch.setattr("deerflow.config.paths._paths_instance", paths, raising=False)

    # Also patch get_paths() return value
    import deerflow.config.paths as paths_module

    monkeypatch.setattr(paths_module, "get_paths", lambda: paths)
    # Patch the lazy getter inside session_memory module
    import deerflow.subagents.session_memory as sm_module

    monkeypatch.setattr(sm_module, "_paths", lambda: paths)
    return tmp_path


# ---------------------------------------------------------------------------
# load_session_context — no prior sessions
# ---------------------------------------------------------------------------


def test_load_session_context_empty(temp_base_dir):
    from deerflow.subagents.session_memory import load_session_context

    result = load_session_context("thread-001", "trial-statistics")
    assert result is None


# ---------------------------------------------------------------------------
# save_session_entry → load_session_context round-trip
# ---------------------------------------------------------------------------


def test_save_and_load_single_entry(temp_base_dir):
    from deerflow.subagents.session_memory import load_session_context, save_session_entry

    save_session_entry(
        thread_id="thread-001",
        subagent_name="trial-statistics",
        task_id="t1",
        prompt_digest="Compute sample size for Phase 2b",
        summary="N=180/arm based on MMRM, alpha=0.05, power=80%",
        key_insights=["Dropout rate 20%", "OBF boundary at 50% IA"],
        output_files=["/mnt/user-data/outputs/sap.docx"],
    )

    ctx = load_session_context("thread-001", "trial-statistics")
    assert ctx is not None
    assert "N=180/arm" in ctx
    assert "Dropout rate 20%" in ctx
    assert "Prior sessions" in ctx


def test_save_multiple_entries_accumulates(temp_base_dir):
    from deerflow.subagents.session_memory import load_session_context, save_session_entry

    save_session_entry("t1", "pharmacology", "task-a", "PK pred", "Cmax=500 nM", ["t1/2=8h"], [])
    save_session_entry("t1", "pharmacology", "task-b", "DDI pred", "CYP3A4 inhibitor", ["AUC ratio 1.8x"], [])

    ctx = load_session_context("t1", "pharmacology")
    assert ctx is not None
    assert "Cmax=500 nM" in ctx
    assert "CYP3A4 inhibitor" in ctx


# ---------------------------------------------------------------------------
# Different subagents have independent session files
# ---------------------------------------------------------------------------


def test_separate_subagents_independent(temp_base_dir):
    from deerflow.subagents.session_memory import load_session_context, save_session_entry

    save_session_entry("thread-x", "trial-statistics", "ts1", "stats", "N=200", ["α=0.05"], [])
    save_session_entry("thread-x", "pharmacology", "pk1", "pk", "Cl=5 L/h", [], [])

    ctx_stats = load_session_context("thread-x", "trial-statistics")
    ctx_pk = load_session_context("thread-x", "pharmacology")

    assert "N=200" in ctx_stats
    assert "N=200" not in ctx_pk
    assert "Cl=5 L/h" in ctx_pk


# ---------------------------------------------------------------------------
# Atomic write creates correct JSON structure
# ---------------------------------------------------------------------------


def test_atomic_write_json_structure(temp_base_dir):
    from deerflow.subagents.session_memory import save_session_entry

    save_session_entry("thread-z", "chemistry", "chem-1", "CMC analysis", "Drug substance purity >99%", ["ICH Q3A compliant"], [])

    from deerflow.config.paths import get_paths

    paths = get_paths()
    session_file = paths.subagent_session_file("thread-z", "chemistry")
    assert session_file.exists()

    with open(session_file) as f:
        data = json.load(f)

    assert data["task_count"] == 1
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["task_id"] == "chem-1"
    assert "Drug substance purity" in data["accumulated_context"]


# ---------------------------------------------------------------------------
# prompt_digest is truncated at 200 chars
# ---------------------------------------------------------------------------


def test_prompt_digest_truncated(temp_base_dir):
    from deerflow.subagents.session_memory import save_session_entry
    from deerflow.config.paths import get_paths

    long_prompt = "A" * 500
    save_session_entry("thread-t", "toxicology", "tox-1", long_prompt, "NOAEL=50 mg/kg", [], [])

    paths = get_paths()
    with open(paths.subagent_session_file("thread-t", "toxicology")) as f:
        data = json.load(f)

    digest = data["tasks"][0]["prompt_digest"]
    assert len(digest) <= 200
