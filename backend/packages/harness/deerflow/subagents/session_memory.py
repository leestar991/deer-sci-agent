"""Per-subagent session memory for within-thread context accumulation.

Each subagent maintains a JSON file under:
  {thread_dir}/subagent_sessions/{subagent_name}.json

This allows repeated calls to the same subagent within one thread to carry forward
an accumulated context summary, enabling true "session continuity".
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


def _paths():
    from deerflow.config.paths import get_paths

    return get_paths()


# ---------------------------------------------------------------------------
# JSON structure helpers
# ---------------------------------------------------------------------------

def _load_raw(session_file: Path) -> dict:
    """Load raw session JSON from disk, returning empty structure if missing."""
    if not session_file.exists():
        return {"task_count": 0, "accumulated_context": "", "tasks": []}
    try:
        with open(session_file, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"task_count": 0, "accumulated_context": "", "tasks": []}


def _atomic_write(session_file: Path, data: dict) -> None:
    """Write data atomically via temp file + rename."""
    session_file.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=session_file.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, session_file)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def load_session_context(thread_id: str, subagent_name: str) -> str | None:
    """Return accumulated context string for this subagent in this thread.

    Returns None if no prior sessions exist (first call).
    """
    session_file = _paths().subagent_session_file(thread_id, subagent_name)
    data = _load_raw(session_file)
    ctx = data.get("accumulated_context", "").strip()
    if not ctx:
        return None
    task_count = data.get("task_count", 0)
    return f"[Prior sessions in this thread: {task_count}]\n{ctx}"


def save_session_entry(
    thread_id: str,
    subagent_name: str,
    task_id: str,
    prompt_digest: str,
    summary: str,
    key_insights: list[str],
    output_files: list[str],
) -> None:
    """Append a completed task entry and refresh accumulated_context.

    Uses atomic write (temp + rename) for crash safety.
    """
    session_file = _paths().subagent_session_file(thread_id, subagent_name)
    data = _load_raw(session_file)

    entry = {
        "task_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_digest": prompt_digest[:200],
        "summary": summary,
        "key_insights": key_insights,
        "output_files": output_files,
    }
    tasks: list[dict] = data.get("tasks", [])
    tasks.append(entry)

    # Rebuild accumulated_context from all tasks (newest last)
    parts: list[str] = []
    for t in tasks:
        ts = t.get("timestamp", "")[:19].replace("T", " ")
        parts.append(f"[{ts}] {t.get('summary', '')}")
        for ins in t.get("key_insights", []):
            parts.append(f"  - {ins}")
    accumulated = "\n".join(parts)

    data["task_count"] = len(tasks)
    data["tasks"] = tasks
    data["accumulated_context"] = accumulated
    data.setdefault("subagent_name", subagent_name)
    data.setdefault("thread_id", thread_id)

    _atomic_write(session_file, data)
