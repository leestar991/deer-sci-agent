"""Middleware to fix dangling tool calls in message history.

A dangling tool call occurs when an AIMessage contains tool_calls but there are
no corresponding ToolMessages in the history (e.g., due to user interruption or
request cancellation). This causes LLM errors due to incomplete message format.

This middleware intercepts the model call to detect and patch such gaps by
inserting synthetic ToolMessages with an error indicator immediately after the
AIMessage that made the tool calls, ensuring correct message ordering.

Note: Uses wrap_model_call instead of before_model to ensure patches are inserted
at the correct positions (immediately after each dangling AIMessage), not appended
to the end of the message list as before_model + add_messages reducer would do.
"""

import logging
from collections.abc import Awaitable, Callable
from typing import override

from langchain.agents import AgentState
from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelCallResult, ModelRequest, ModelResponse
from langchain_core.messages import ToolMessage

logger = logging.getLogger(__name__)


class DanglingToolCallMiddleware(AgentMiddleware[AgentState]):
    """Inserts placeholder ToolMessages for dangling tool calls before model invocation.

    Scans the message history for AIMessages whose tool_calls lack corresponding
    ToolMessages, and injects synthetic error responses immediately after the
    offending AIMessage so the LLM receives a well-formed conversation.
    """

    def _build_patched_messages(self, messages: list) -> list | None:
        """Return a new message list with patches inserted at the correct positions.

        For each AIMessage with tool_calls, checks that the IMMEDIATELY FOLLOWING
        messages are ToolMessages for ALL of those tool_calls. If any tool_call
        lacks a ToolMessage immediately after the AIMessage (either missing entirely
        or displaced by an intervening non-ToolMessage), a synthetic ToolMessage is
        inserted right after that AIMessage.

        This handles two cases:
        1. Missing ToolMessages (e.g. run interrupted before ToolNode ran).
        2. Displaced ToolMessages (e.g. a HumanMessage injected between AIMessage
           and ToolMessages by LoopDetectionMiddleware), which would cause providers
           like Anthropic to reject the request with "tool_result not immediately
           after tool_use".

        Returns None if no patches are needed.
        """
        # --- Pass 1: determine which AIMessages need patching ---------------
        # An AIMessage needs patching when at least one of its tool_call IDs does
        # NOT have a corresponding ToolMessage in the immediately-following block
        # of consecutive ToolMessages.

        needs_patch = False
        for i, msg in enumerate(messages):
            if getattr(msg, "type", None) != "ai":
                continue
            tool_calls = getattr(msg, "tool_calls", None) or []
            if not tool_calls:
                continue

            # Collect tool_call IDs that appear in the immediately-following
            # consecutive ToolMessage block.
            immediately_after_ids: set[str] = set()
            j = i + 1
            while j < len(messages) and isinstance(messages[j], ToolMessage):
                tc_id = messages[j].tool_call_id
                if tc_id:
                    immediately_after_ids.add(tc_id)
                j += 1

            for tc in tool_calls:
                tc_id = tc.get("id")
                if tc_id and tc_id not in immediately_after_ids:
                    needs_patch = True
                    break
            if needs_patch:
                break

        if not needs_patch:
            return None

        # --- Pass 2: rebuild with patches ------------------------------------
        # For each AIMessage whose tool_calls lack immediately-following
        # ToolMessages, inject synthetic ones right after it.
        # Any existing (but displaced) ToolMessages whose IDs are covered by
        # synthetic ones are dropped to avoid duplicates.

        # Pre-collect all ToolMessage IDs that will be synthetically added,
        # so we can skip their displaced originals in the output.
        synth_ids: set[str] = set()
        for i, msg in enumerate(messages):
            if getattr(msg, "type", None) != "ai":
                continue
            tool_calls = getattr(msg, "tool_calls", None) or []
            if not tool_calls:
                continue
            immediately_after_ids: set[str] = set()
            j = i + 1
            while j < len(messages) and isinstance(messages[j], ToolMessage):
                tc_id = messages[j].tool_call_id
                if tc_id:
                    immediately_after_ids.add(tc_id)
                j += 1
            for tc in tool_calls:
                tc_id = tc.get("id")
                if tc_id and tc_id not in immediately_after_ids:
                    synth_ids.add(tc_id)

        patched: list = []
        patch_count = 0
        for i, msg in enumerate(messages):
            # Drop displaced ToolMessages whose IDs are covered by synthetic ones.
            if isinstance(msg, ToolMessage) and msg.tool_call_id in synth_ids:
                patch_count += 1  # counted as replaced, not double-counted
                continue

            patched.append(msg)

            if getattr(msg, "type", None) != "ai":
                continue
            tool_calls = getattr(msg, "tool_calls", None) or []
            if not tool_calls:
                continue

            immediately_after_ids: set[str] = set()
            j = i + 1
            while j < len(messages) and isinstance(messages[j], ToolMessage):
                tc_id = messages[j].tool_call_id
                if tc_id:
                    immediately_after_ids.add(tc_id)
                j += 1

            for tc in tool_calls:
                tc_id = tc.get("id")
                if tc_id and tc_id not in immediately_after_ids:
                    patched.append(
                        ToolMessage(
                            content="[Tool call was interrupted and did not return a result.]",
                            tool_call_id=tc_id,
                            name=tc.get("name", "unknown"),
                            status="error",
                        )
                    )

        logger.warning(f"Patched {patch_count} ToolMessage(s) for displaced/missing tool calls")
        return patched

    @override
    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        patched = self._build_patched_messages(request.messages)
        if patched is not None:
            request = request.override(messages=patched)
        return handler(request)

    @override
    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        patched = self._build_patched_messages(request.messages)
        if patched is not None:
            request = request.override(messages=patched)
        return await handler(request)
