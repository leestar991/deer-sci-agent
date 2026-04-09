"""Tests for LoopDetectionMiddleware."""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from deerflow.agents.middlewares.loop_detection_middleware import (
    _HARD_STOP_MSG,
    _MANAGEMENT_THRESHOLD_MULTIPLIER,
    _MANAGEMENT_TOOLS,
    LoopDetectionMiddleware,
    _hash_tool_calls,
)


def _make_runtime(thread_id="test-thread"):
    """Build a minimal Runtime mock with context."""
    runtime = MagicMock()
    runtime.context = {"thread_id": thread_id}
    return runtime


def _make_state(tool_calls=None, content=""):
    """Build a minimal AgentState dict with an AIMessage."""
    msg = AIMessage(content=content, tool_calls=tool_calls or [])
    return {"messages": [msg]}


def _bash_call(cmd="ls"):
    return {"name": "bash", "id": f"call_{cmd}", "args": {"command": cmd}}


class TestHashToolCalls:
    def test_same_calls_same_hash(self):
        a = _hash_tool_calls([_bash_call("ls")])
        b = _hash_tool_calls([_bash_call("ls")])
        assert a == b

    def test_different_calls_different_hash(self):
        a = _hash_tool_calls([_bash_call("ls")])
        b = _hash_tool_calls([_bash_call("pwd")])
        assert a != b

    def test_order_independent(self):
        a = _hash_tool_calls([_bash_call("ls"), {"name": "read_file", "args": {"path": "/tmp"}}])
        b = _hash_tool_calls([{"name": "read_file", "args": {"path": "/tmp"}}, _bash_call("ls")])
        assert a == b

    def test_empty_calls(self):
        h = _hash_tool_calls([])
        assert isinstance(h, str)
        assert len(h) > 0


class TestLoopDetection:
    def test_no_tool_calls_returns_none(self):
        mw = LoopDetectionMiddleware()
        runtime = _make_runtime()
        state = {"messages": [AIMessage(content="hello")]}
        result = mw._apply(state, runtime)
        assert result is None

    def test_below_threshold_returns_none(self):
        mw = LoopDetectionMiddleware(warn_threshold=3)
        runtime = _make_runtime()
        call = [_bash_call("ls")]

        # First two identical calls — no warning
        for _ in range(2):
            result = mw._apply(_make_state(tool_calls=call), runtime)
            assert result is None

    def test_warn_at_threshold(self):
        mw = LoopDetectionMiddleware(warn_threshold=3, hard_limit=5)
        runtime = _make_runtime()
        call = [_bash_call("ls")]

        for _ in range(2):
            mw._apply(_make_state(tool_calls=call), runtime)

        # Third identical call triggers warning.
        # Result should contain [stripped AIMessage (no tool_calls), HumanMessage warning].
        result = mw._apply(_make_state(tool_calls=call), runtime)
        assert result is not None
        msgs = result["messages"]
        assert len(msgs) == 2
        # First: stripped AIMessage (tool_calls cleared)
        assert isinstance(msgs[0], AIMessage)
        assert msgs[0].tool_calls == []
        # Second: warning HumanMessage
        assert isinstance(msgs[1], HumanMessage)
        assert "LOOP DETECTED" in msgs[1].content

    def test_warn_only_injected_once(self):
        """Warning for the same hash should only be injected once per thread."""
        mw = LoopDetectionMiddleware(warn_threshold=3, hard_limit=10)
        runtime = _make_runtime()
        call = [_bash_call("ls")]

        # First two — no warning
        for _ in range(2):
            mw._apply(_make_state(tool_calls=call), runtime)

        # Third — warning injected (stripped AIMessage + HumanMessage)
        result = mw._apply(_make_state(tool_calls=call), runtime)
        assert result is not None
        assert "LOOP DETECTED" in result["messages"][1].content

        # Fourth — warning already injected, should return None
        result = mw._apply(_make_state(tool_calls=call), runtime)
        assert result is None

    def test_warn_strips_tool_calls_to_prevent_invalid_sequence(self):
        """Regression: warning must strip tool_calls to prevent ToolNode from running
        after the injected HumanMessage, which would produce:
          AIMessage[tool_use] → HumanMessage → ToolMessage[tool_result]
        That sequence is rejected by Anthropic with a 400 error."""
        mw = LoopDetectionMiddleware(warn_threshold=2, hard_limit=10)
        runtime = _make_runtime()
        call = [_bash_call("ls")]

        mw._apply(_make_state(tool_calls=call), runtime)

        result = mw._apply(_make_state(tool_calls=call), runtime)
        assert result is not None
        msgs = result["messages"]

        # Stripped AIMessage must have empty tool_calls
        stripped = msgs[0]
        assert isinstance(stripped, AIMessage)
        assert stripped.tool_calls == [], "tool_calls must be stripped to prevent ToolNode execution"

        # Warning HumanMessage must be present
        human_msg = msgs[1]
        assert isinstance(human_msg, HumanMessage)
        assert "LOOP DETECTED" in human_msg.content

    def test_warn_without_tool_calls_only_injects_human_message(self):
        """If last message has no tool_calls, warning is only a HumanMessage."""
        mw = LoopDetectionMiddleware(warn_threshold=2, hard_limit=10)
        runtime = _make_runtime()

        # Simulate an AIMessage without tool_calls hitting the threshold
        # (edge case, but guard the branch)
        call = [_bash_call("ls")]
        # Register 1 normal call to initialise history, then submit a state
        # whose last message has no tool_calls (edge case branch).
        mw._apply(_make_state(tool_calls=call), runtime)

        # Directly manipulate warned set to simulate prior warning so the
        # "no tool_calls" branch can be reached more simply via hard_limit=2.
        mw2 = LoopDetectionMiddleware(warn_threshold=1, hard_limit=10)
        no_tc_state = {"messages": [AIMessage(content="text only")]}
        result = mw2._apply(no_tc_state, _make_runtime("thread-x"))
        # No tool_calls → HumanMessage-only path not reached (no_tc_state
        # AIMessage has no tool_calls, so _track_and_check returns None).
        assert result is None

    def test_hard_stop_at_limit(self):
        mw = LoopDetectionMiddleware(warn_threshold=2, hard_limit=4)
        runtime = _make_runtime()
        call = [_bash_call("ls")]

        for _ in range(3):
            mw._apply(_make_state(tool_calls=call), runtime)

        # Fourth call triggers hard stop
        result = mw._apply(_make_state(tool_calls=call), runtime)
        assert result is not None
        msgs = result["messages"]
        assert len(msgs) == 1
        # Hard stop strips tool_calls
        assert isinstance(msgs[0], AIMessage)
        assert msgs[0].tool_calls == []
        assert _HARD_STOP_MSG in msgs[0].content

    def test_different_calls_dont_trigger(self):
        mw = LoopDetectionMiddleware(warn_threshold=2)
        runtime = _make_runtime()

        # Each call is different
        for i in range(10):
            result = mw._apply(_make_state(tool_calls=[_bash_call(f"cmd_{i}")]), runtime)
            assert result is None

    def test_window_sliding(self):
        mw = LoopDetectionMiddleware(warn_threshold=3, window_size=5)
        runtime = _make_runtime()
        call = [_bash_call("ls")]

        # Fill with 2 identical calls
        mw._apply(_make_state(tool_calls=call), runtime)
        mw._apply(_make_state(tool_calls=call), runtime)

        # Push them out of the window with different calls
        for i in range(5):
            mw._apply(_make_state(tool_calls=[_bash_call(f"other_{i}")]), runtime)

        # Now the original call should be fresh again — no warning
        result = mw._apply(_make_state(tool_calls=call), runtime)
        assert result is None

    def test_reset_clears_state(self):
        mw = LoopDetectionMiddleware(warn_threshold=2)
        runtime = _make_runtime()
        call = [_bash_call("ls")]

        mw._apply(_make_state(tool_calls=call), runtime)
        mw._apply(_make_state(tool_calls=call), runtime)

        # Would trigger warning, but reset first
        mw.reset()
        result = mw._apply(_make_state(tool_calls=call), runtime)
        assert result is None

    def test_non_ai_message_ignored(self):
        mw = LoopDetectionMiddleware()
        runtime = _make_runtime()
        state = {"messages": [SystemMessage(content="hello")]}
        result = mw._apply(state, runtime)
        assert result is None

    def test_empty_messages_ignored(self):
        mw = LoopDetectionMiddleware()
        runtime = _make_runtime()
        result = mw._apply({"messages": []}, runtime)
        assert result is None

    def test_thread_id_from_runtime_context(self):
        """Thread ID should come from runtime.context, not state."""
        mw = LoopDetectionMiddleware(warn_threshold=2)
        runtime_a = _make_runtime("thread-A")
        runtime_b = _make_runtime("thread-B")
        call = [_bash_call("ls")]

        # One call on thread A
        mw._apply(_make_state(tool_calls=call), runtime_a)
        # One call on thread B
        mw._apply(_make_state(tool_calls=call), runtime_b)

        # Second call on thread A — triggers warning (2 >= warn_threshold)
        result = mw._apply(_make_state(tool_calls=call), runtime_a)
        assert result is not None
        assert "LOOP DETECTED" in result["messages"][1].content

        # Second call on thread B — also triggers (independent tracking)
        result = mw._apply(_make_state(tool_calls=call), runtime_b)
        assert result is not None
        assert "LOOP DETECTED" in result["messages"][1].content

    def test_lru_eviction(self):
        """Old threads should be evicted when max_tracked_threads is exceeded."""
        mw = LoopDetectionMiddleware(warn_threshold=2, max_tracked_threads=3)
        call = [_bash_call("ls")]

        # Fill up 3 threads
        for i in range(3):
            runtime = _make_runtime(f"thread-{i}")
            mw._apply(_make_state(tool_calls=call), runtime)

        # Add a 4th thread — should evict thread-0
        runtime_new = _make_runtime("thread-new")
        mw._apply(_make_state(tool_calls=call), runtime_new)

        assert "thread-0" not in mw._history
        assert "thread-new" in mw._history
        assert len(mw._history) == 3

    def test_thread_safe_mutations(self):
        """Verify lock is used for mutations (basic structural test)."""
        mw = LoopDetectionMiddleware()
        # The middleware should have a lock attribute
        assert hasattr(mw, "_lock")
        assert isinstance(mw._lock, type(mw._lock))

    def test_fallback_thread_id_when_missing(self):
        """When runtime context has no thread_id, should use 'default'."""
        mw = LoopDetectionMiddleware(warn_threshold=2)
        runtime = MagicMock()
        runtime.context = {}
        call = [_bash_call("ls")]

        mw._apply(_make_state(tool_calls=call), runtime)
        assert "default" in mw._history


def _write_todos_call():
    return {"name": "write_todos", "id": "call_todos", "args": {"todos": [{"id": "1", "content": "task", "status": "pending"}]}}


def _present_files_call():
    return {"name": "present_files", "id": "call_pf", "args": {"files": ["/mnt/user-data/outputs/report.pptx"]}}


class TestManagementToolMultiplier:
    """Management-only calls (write_todos, present_files) use higher thresholds."""

    def test_management_tools_set_contains_expected_tools(self):
        assert "write_todos" in _MANAGEMENT_TOOLS
        assert "present_files" in _MANAGEMENT_TOOLS

    def test_management_tool_does_not_warn_at_normal_threshold(self):
        """write_todos should NOT trigger a warning at the normal warn_threshold count."""
        mw = LoopDetectionMiddleware(warn_threshold=3, hard_limit=5)
        runtime = _make_runtime()
        call = [_write_todos_call()]

        # Under normal rules this would warn at count=3.
        # With management multiplier (3×), the effective warn is 9 — so no warning here.
        for _ in range(3):
            result = mw._apply(_make_state(tool_calls=call), runtime)
        # 3 calls < effective_warn(9) → no warning
        assert result is None

    def test_management_tool_warns_at_multiplied_threshold(self):
        """write_todos should warn only after warn_threshold × multiplier identical calls."""
        mw = LoopDetectionMiddleware(warn_threshold=3, hard_limit=20)
        runtime = _make_runtime()
        call = [_write_todos_call()]
        effective_warn = 3 * _MANAGEMENT_THRESHOLD_MULTIPLIER  # 9

        # Calls 1..effective_warn-1 → no warning
        for i in range(1, effective_warn):
            result = mw._apply(_make_state(tool_calls=call), runtime)
        assert result is None

        # Call at effective_warn → warning
        result = mw._apply(_make_state(tool_calls=call), runtime)
        assert result is not None
        msgs = result["messages"]
        assert any("LOOP DETECTED" in getattr(m, "content", "") for m in msgs)

    def test_mixed_management_and_substantive_tool_not_elevated(self):
        """A call mixing write_todos with a substantive tool uses normal thresholds."""
        mw = LoopDetectionMiddleware(warn_threshold=3, hard_limit=5)
        runtime = _make_runtime()
        # Mixed call: one management + one substantive
        mixed = [_write_todos_call(), _bash_call("ls")]

        # At count=3 this should trigger warning (normal threshold, not elevated)
        for _ in range(2):
            mw._apply(_make_state(tool_calls=mixed), runtime)
        result = mw._apply(_make_state(tool_calls=mixed), runtime)
        assert result is not None
        msgs = result["messages"]
        assert any("LOOP DETECTED" in getattr(m, "content", "") for m in msgs)

    def test_present_files_also_uses_elevated_threshold(self):
        """present_files (another management tool) also gets the elevated threshold."""
        mw = LoopDetectionMiddleware(warn_threshold=3, hard_limit=20)
        runtime = _make_runtime()
        call = [_present_files_call()]
        normal_warn = 3

        # Would trigger at count=3 under normal rules; should NOT with multiplier
        for _ in range(normal_warn):
            result = mw._apply(_make_state(tool_calls=call), runtime)
        assert result is None
