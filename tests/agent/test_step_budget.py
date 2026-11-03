"""
Tests for the copilot step budget.

The budget is the LangGraph recursion limit of one user turn. It defaults
per copilot mode and can be overridden with max_steps in the LLM model
config. When the budget runs out the graph makes one final summary call
without tools instead of ending silently on a tool result.
"""

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from gns3server.agent.gns3_copilot.agent import gns3_copilot as mod


class TestResolveRecursionLimit:
    def test_mode_defaults(self):
        assert mod.resolve_recursion_limit(None) == 25
        assert mod.resolve_recursion_limit({}) == 25
        assert mod.resolve_recursion_limit({"copilot_mode": "teaching_assistant"}) == 25
        assert mod.resolve_recursion_limit({"copilot_mode": "lab_automation_assistant"}) == 50
        assert mod.resolve_recursion_limit({"copilot_mode": "troubleshooting_injection"}) == 100

    def test_unknown_mode_falls_back(self):
        assert mod.resolve_recursion_limit({"copilot_mode": "something_new"}) == 25

    def test_max_steps_overrides_the_mode_default(self):
        assert mod.resolve_recursion_limit({"copilot_mode": "lab_automation_assistant", "max_steps": 40}) == 40
        assert mod.resolve_recursion_limit({"copilot_mode": "teaching_assistant", "max_steps": "60"}) == 60

    @pytest.mark.parametrize("value", [0, -5, "abc", None, [1]])
    def test_invalid_max_steps_falls_back_to_the_default(self, value):
        assert mod.resolve_recursion_limit({"copilot_mode": "lab_automation_assistant", "max_steps": value}) == 50


def _tool_message() -> ToolMessage:
    return ToolMessage(content='{"ok": true}', tool_call_id="call-1")


class TestRecursionLimitContinue:
    def test_tools_done_with_budget_left_continue(self):
        state = {"messages": [_tool_message()], "remaining_steps": 5, "session_id": None}
        assert mod.recursion_limit_continue(state) == "llm_call"

    def test_tools_done_with_low_budget_wrap_up(self):
        state = {"messages": [_tool_message()], "remaining_steps": 3, "session_id": None}
        assert mod.recursion_limit_continue(state) == "budget_wrapup"

    def test_non_tool_message_ends(self):
        state = {"messages": [AIMessage(content="done")], "remaining_steps": 5, "session_id": None}
        assert mod.recursion_limit_continue(state) == mod.END

    def test_abort_ends(self):
        mod.set_abort_flag("abort-session")
        try:
            state = {"messages": [_tool_message()], "remaining_steps": 5, "session_id": "abort-session"}
            assert mod.recursion_limit_continue(state) == mod.END
        finally:
            mod.clear_abort_flag("abort-session")


class TestBudgetWrapup:
    def test_wrapup_sets_the_flag(self):
        out = mod.budget_wrapup({"messages": [_tool_message()], "remaining_steps": 3, "session_id": "s1"})
        assert out["budget_exhausted"] is True
        assert out["session_id"] == "s1"

    def test_wrapup_call_binds_no_tools_and_injects_the_instruction(self, monkeypatch):
        captured = {}

        class FakeModel:
            def invoke(self, messages):
                captured["messages"] = messages
                return AIMessage(content="Summary: stopped before verification.")

        monkeypatch.setattr(
            mod,
            "get_current_llm_config",
            lambda: {"provider": "fake", "model": "fake", "copilot_mode": "lab_automation_assistant"},
        )
        monkeypatch.setattr(mod, "load_system_prompt", lambda config: "system prompt")
        monkeypatch.setattr(mod, "create_pre_model_hook", lambda **kwargs: lambda state: state)
        monkeypatch.setattr(mod, "create_base_model", lambda config: FakeModel())

        def fail_if_tools_bound(*args, **kwargs):
            raise AssertionError("tools must not be bound for the wrap-up call")

        monkeypatch.setattr(mod, "create_base_model_with_tools", fail_if_tools_bound)

        state = {
            "messages": [HumanMessage(content="build the lab")],
            "budget_exhausted": True,
            "llm_calls": 3,
            "session_id": "s1",
        }
        out = mod.llm_call(state)

        assert out["messages"][0].content == "Summary: stopped before verification."
        assert out["llm_calls"] == 4
        assert captured["messages"][-1].content == mod.BUDGET_WRAPUP_INSTRUCTION

    def test_should_continue_ends_without_title_after_wrapup(self):
        state = {
            "messages": [AIMessage(content="Summary")],
            "budget_exhausted": True,
            "conversation_title": None,
            "session_id": None,
        }
        assert mod.should_continue(state) == mod.END


def test_stream_inputs_do_not_carry_the_dead_remaining_steps():
    """RemainingSteps is a managed value: an input for it is ignored.

    Passing it looked like a second budget knob but never did anything.
    """
    from pathlib import Path

    source = Path(mod.__file__).parent.parent / "agent_service.py"
    assert '"remaining_steps"' not in source.read_text()
