"""Per-thread shared memory — aggregates results from all subagents.

Stored at:
  {thread_dir}/shared_memory.json

All completed subagent tasks write a summary entry here. The Lead Agent
(or the aggregate_results tool) can read these entries to synthesise a
cross-subagent view of the work done so far.

Concurrent writes are serialised via a per-file advisory lock so parallel
subagents do not corrupt the shared JSON.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _paths():
    from deerflow.config.paths import get_paths

    return get_paths()


# ---------------------------------------------------------------------------
# Low-level I/O helpers
# ---------------------------------------------------------------------------

def _load_raw(shared_file: Path) -> dict:
    """Load JSON from disk; return empty structure if missing or corrupt."""
    if not shared_file.exists():
        return {"entries": []}
    try:
        with open(shared_file, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"entries": []}


def _atomic_write(shared_file: Path, data: dict) -> None:
    """Write data atomically via temp file + rename."""
    shared_file.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=shared_file.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, shared_file)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def append_entry(
    thread_id: str,
    task_id: str,
    subagent_name: str,
    summary: str,
    key_findings: list[str],
    output_files: list[str],
    metadata: dict | None = None,
) -> None:
    """Append a completed-task entry to the thread's shared memory.

    Thread-safe: uses an advisory file lock so concurrent subagents don't
    corrupt the JSON during simultaneous writes.
    """
    shared_file = _paths().shared_memory_file(thread_id)
    shared_file.parent.mkdir(parents=True, exist_ok=True)

    lock_path = shared_file.with_suffix(".lock")
    with open(lock_path, "w") as lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        try:
            data = _load_raw(shared_file)
            entry = {
                "entry_id": str(uuid.uuid4())[:8],
                "task_id": task_id,
                "subagent_name": subagent_name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "summary": summary,
                "key_findings": key_findings,
                "output_files": output_files,
                "metadata": metadata or {},
            }
            data.setdefault("thread_id", thread_id)
            data.setdefault("entries", [])
            data["entries"].append(entry)
            _atomic_write(shared_file, data)
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)


def read_entries(
    thread_id: str,
    task_ids: list[str] | None = None,
    subagent_names: list[str] | None = None,
) -> list[dict]:
    """Read shared memory entries, optionally filtered by task_ids or subagent_names.

    Returns an empty list if the shared memory file does not exist yet.
    """
    shared_file = _paths().shared_memory_file(thread_id)
    data = _load_raw(shared_file)
    entries: list[dict] = data.get("entries", [])

    if task_ids is not None:
        task_id_set = set(task_ids)
        entries = [e for e in entries if e.get("task_id") in task_id_set]
    if subagent_names is not None:
        name_set = set(subagent_names)
        entries = [e for e in entries if e.get("subagent_name") in name_set]

    return entries
