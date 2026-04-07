"""Aggregate results tool — synthesises outputs from multiple completed subagent tasks.

Reads entries from the thread's shared_memory.json and applies one of three strategies:
  - merge: Synthesise all outputs into a unified conclusion/document.
  - vote: Identify majority agreement across subagent findings on a topic.
  - adjudicate: Surface conflicts between subagent outputs and resolve them with reasoning.
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from langchain.tools import InjectedToolCallId, ToolRuntime, tool
from langgraph.typing import ContextT

# ThreadState is imported at module level so the @tool decorator can resolve type hints.
# This module is always imported lazily (inside get_available_tools()) to avoid circular
# imports — by that time deerflow.agents is already fully initialised.
from deerflow.agents.thread_state import ThreadState

logger = logging.getLogger(__name__)

_MERGE_PROMPT = """You are synthesising outputs from multiple domain expert subagents.

Topic / question: {topic}

Subagent outputs:
{summaries}

Produce a concise unified conclusion that integrates all perspectives. Highlight agreements,
note any nuances, and flag any gaps. Output in clear structured prose (markdown allowed)."""

_VOTE_PROMPT = """You are analysing outputs from multiple domain expert subagents to determine
the majority position on a specific topic.

Topic / question: {topic}

Subagent findings:
{summaries}

Tally the positions, identify the majority view (≥50%+1), and briefly explain the reasoning
behind the consensus. List any minority positions with their rationale."""

_ADJUDICATE_PROMPT = """You are resolving conflicts among outputs from multiple domain expert subagents.

Topic / question: {topic}

Subagent outputs:
{summaries}

1. Identify any factual or methodological conflicts.
2. Evaluate each conflicting claim using evidence cited.
3. Provide a reasoned adjudication — which position is best supported and why.
4. Where no definitive answer is possible, state what additional information is needed."""


def _format_summaries(entries: list[dict]) -> str:
    lines: list[str] = []
    for i, e in enumerate(entries, 1):
        name = e.get("subagent_name", "unknown")
        summary = e.get("summary", "")
        findings = e.get("key_findings", [])
        lines.append(f"--- Subagent {i}: {name} ---")
        lines.append(summary)
        for f in findings:
            lines.append(f"  • {f}")
        lines.append("")
    return "\n".join(lines)


@tool("aggregate_results", parse_docstring=True)
async def aggregate_results_tool(
    runtime: ToolRuntime[ContextT, ThreadState],
    tool_call_id: Annotated[str, InjectedToolCallId],
    topic: str,
    strategy: Literal["vote", "merge", "adjudicate"] = "merge",
    task_ids: list[str] | None = None,
    subagent_names: list[str] | None = None,
) -> str:
    """Aggregate and synthesise results from previously completed subagent tasks.

    Reads the thread's shared memory (written by each completed subagent task) and
    applies the requested strategy to produce a unified conclusion.

    Args:
        topic: The question or topic that the aggregation should address.
        strategy: How to combine results — "merge" (synthesise), "vote" (majority),
                  or "adjudicate" (resolve conflicts).
        task_ids: Optional list of task_ids to include (default: all entries).
        subagent_names: Optional list of subagent names to filter by.
        tool_call_id: Injected tool-call id (do not pass manually).
    """
    # Resolve thread_id from runtime context / configurable
    thread_id: str | None = None
    parent_model: str | None = None
    if runtime is not None:
        thread_id = runtime.context.get("thread_id") if runtime.context else None
        if thread_id is None:
            thread_id = runtime.config.get("configurable", {}).get("thread_id")
        parent_model = (runtime.config.get("metadata") or {}).get("model_name")

    if not thread_id:
        return "Error: Cannot determine thread_id for shared memory access."

    # Load entries from shared memory
    try:
        from deerflow.subagents.shared_memory import read_entries

        entries = read_entries(thread_id, task_ids=task_ids, subagent_names=subagent_names)
    except Exception as e:
        logger.warning(f"aggregate_results: failed to read shared memory: {e}")
        return f"Error reading shared memory: {e}"

    if not entries:
        return "No subagent results found in shared memory for this thread. Run at least one subagent task first."

    summaries_text = _format_summaries(entries)

    # Build the strategy prompt
    if strategy == "vote":
        prompt_text = _VOTE_PROMPT.format(topic=topic, summaries=summaries_text)
    elif strategy == "adjudicate":
        prompt_text = _ADJUDICATE_PROMPT.format(topic=topic, summaries=summaries_text)
    else:  # merge (default)
        prompt_text = _MERGE_PROMPT.format(topic=topic, summaries=summaries_text)

    # Invoke LLM with parent's model
    try:
        from deerflow.models import create_chat_model

        model = create_chat_model(parent_model)
        response = await model.ainvoke(prompt_text)
        result_text = response.content if hasattr(response, "content") else str(response)
        if isinstance(result_text, list):
            result_text = " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in result_text)
        return f"[aggregate_results: strategy={strategy}, entries={len(entries)}]\n\n{result_text}"
    except Exception as e:
        logger.exception("aggregate_results: LLM call failed")
        return f"Error during aggregation: {e}"
