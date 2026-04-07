"""Tests for subagent shared memory (per-thread cross-subagent result aggregation)."""

import json
import threading

import pytest


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def patched_paths(tmp_path, monkeypatch):
    from deerflow.config.paths import Paths

    paths = Paths(base_dir=tmp_path)

    import deerflow.config.paths as paths_module

    monkeypatch.setattr(paths_module, "get_paths", lambda: paths)
    import deerflow.subagents.shared_memory as sm_module

    monkeypatch.setattr(sm_module, "_paths", lambda: paths)
    return paths


# ---------------------------------------------------------------------------
# read_entries on empty thread
# ---------------------------------------------------------------------------


def test_read_entries_empty(patched_paths):
    from deerflow.subagents.shared_memory import read_entries

    entries = read_entries("no-such-thread")
    assert entries == []


# ---------------------------------------------------------------------------
# append_entry → read_entries round-trip
# ---------------------------------------------------------------------------


def test_append_and_read_single(patched_paths):
    from deerflow.subagents.shared_memory import append_entry, read_entries

    append_entry(
        thread_id="t1",
        task_id="task-001",
        subagent_name="trial-statistics",
        summary="N=180/arm, MMRM, 80% power",
        key_findings=["Dropout 20%", "IA at 50% info"],
        output_files=["/mnt/user-data/outputs/sap.docx"],
    )

    entries = read_entries("t1")
    assert len(entries) == 1
    assert entries[0]["subagent_name"] == "trial-statistics"
    assert entries[0]["task_id"] == "task-001"
    assert "N=180/arm" in entries[0]["summary"]


def test_append_multiple_entries(patched_paths):
    from deerflow.subagents.shared_memory import append_entry, read_entries

    for i in range(3):
        append_entry(
            thread_id="t2",
            task_id=f"task-{i}",
            subagent_name="pharmacology",
            summary=f"Summary {i}",
            key_findings=[],
            output_files=[],
        )

    entries = read_entries("t2")
    assert len(entries) == 3


# ---------------------------------------------------------------------------
# Filtering by task_ids and subagent_names
# ---------------------------------------------------------------------------


def test_filter_by_task_ids(patched_paths):
    from deerflow.subagents.shared_memory import append_entry, read_entries

    append_entry("t3", "task-a", "trial-statistics", "stats result", [], [])
    append_entry("t3", "task-b", "pharmacology", "pk result", [], [])

    filtered = read_entries("t3", task_ids=["task-a"])
    assert len(filtered) == 1
    assert filtered[0]["task_id"] == "task-a"


def test_filter_by_subagent_names(patched_paths):
    from deerflow.subagents.shared_memory import append_entry, read_entries

    append_entry("t4", "task-1", "trial-statistics", "stats", [], [])
    append_entry("t4", "task-2", "pharmacology", "pk", [], [])

    filtered = read_entries("t4", subagent_names=["pharmacology"])
    assert len(filtered) == 1
    assert filtered[0]["subagent_name"] == "pharmacology"


# ---------------------------------------------------------------------------
# Concurrent writes do not corrupt the file
# ---------------------------------------------------------------------------


def test_concurrent_append_safe(patched_paths):
    from deerflow.subagents.shared_memory import append_entry, read_entries

    n_threads = 10
    errors: list[Exception] = []

    def worker(i: int):
        try:
            append_entry(
                thread_id="t-concurrent",
                task_id=f"task-{i}",
                subagent_name=f"agent-{i % 3}",
                summary=f"result {i}",
                key_findings=[],
                output_files=[],
            )
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n_threads)]
    for thr in threads:
        thr.start()
    for thr in threads:
        thr.join()

    assert errors == [], f"Concurrent write errors: {errors}"
    entries = read_entries("t-concurrent")
    assert len(entries) == n_threads


# ---------------------------------------------------------------------------
# JSON structure is valid after multiple appends
# ---------------------------------------------------------------------------


def test_json_structure(patched_paths):
    from deerflow.subagents.shared_memory import append_entry

    append_entry("t5", "task-x", "chemistry", "CMC summary", ["ICH Q3A"], [])

    shared_file = patched_paths.shared_memory_file("t5")
    assert shared_file.exists()
    with open(shared_file) as f:
        data = json.load(f)

    assert data["thread_id"] == "t5"
    assert len(data["entries"]) == 1
    entry = data["entries"][0]
    assert entry["subagent_name"] == "chemistry"
    assert "entry_id" in entry
    assert "timestamp" in entry
