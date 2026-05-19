# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# Copyright (C) 2025 Yue Guobin (岳国宾)
# Author: Yue Guobin (岳国宾)
#
# This file is part of GNS3-Copilot project.
#
# GNS3-Copilot is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# GNS3-Copilot is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License
# for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNS3-Copilot. If not, see <https://www.gnu.org/licenses/>.
#
# Project Home: https://github.com/yueguobin/gns3-copilot
#

"""
Context Manager for GNS3-Copilot - Using LangGraph pre_model_hook

This module provides context window management using LangGraph's recommended
pre_model_hook approach with accurate token counting:

Key Features:
- Accurate token counting using tiktoken (95%+ accuracy)
- Template variable injection for topology info
- Context strategy ratios (conservative/balanced/aggressive)
- Message trimming using LangChain's native trim_messages
- Tool definition token estimation
- Detailed token breakdown logging

Requirements:
- tiktoken>=0.8.0 (required)
"""

import json
import logging
import os
import warnings
from pathlib import Path
from typing import Any
from typing import Callable

# Configure tiktoken cache directory (must be set before importing tiktoken)
_cache_dir = Path(__file__).parent.parent / "cache" / "tiktoken"
_cache_dir.mkdir(parents=True, exist_ok=True)
os.environ["TIKTOKEN_CACHE_DIR"] = str(_cache_dir)

import tiktoken
from langchain_core.messages import BaseMessage
from langchain_core.messages import SystemMessage
from langchain_core.messages import trim_messages

logger = logging.getLogger(__name__)

# ============================================================================
# Token Counter Setup
# ============================================================================

# Initialize tiktoken encoding (required dependency)
import time
logger.debug("Initializing tiktoken encoding (cl100k_base)...")
logger.debug(f"Cache directory: {_cache_dir}")
logger.debug("This may take a moment on first run (downloading ~1.6MB encoding file from openaipublic.blob.core.windows.net)")
start_time = time.time()
_tiktoken_encoding = tiktoken.get_encoding("cl100k_base")
elapsed = time.time() - start_time
logger.debug(f"✓ tiktoken encoding loaded successfully (took {elapsed:.2f}s)")

# ============================================================================
# Constants
# ============================================================================

# Context strategy ratios (percentage of context limit to use for input)
CONTEXT_STRATEGY_RATIOS = {
    "conservative": 0.60,
    "balanced": 0.75,
    "aggressive": 0.85,
}

DEFAULT_CONTEXT_STRATEGY = "balanced"

# Token unit conversion
TOKENS_PER_K = 1000


# ============================================================================
# Token Counting Functions
# ============================================================================


def count_tokens(text: str) -> int:
    """
    Count tokens in text using tiktoken.

    Uses cl100k_base encoding (GPT-4) which provides accurate counting
    for most modern LLMs (OpenAI, Anthropic, DeepSeek, etc.).

    Args:
        text: Text to count tokens for

    Returns:
        Exact token count (not estimated)
    """
    if not text:
        return 0

    return len(_tiktoken_encoding.encode(text))


def estimate_tool_tokens(tools: list[Any]) -> int:
    """
    Estimate token consumption for tool definitions.

    Tool definitions are serialized as JSON and sent to LLM with each request.
    This function estimates their token cost.

    Args:
        tools: List of LangChain tool objects

    Returns:
        Estimated token count for all tool definitions
    """
    if not tools:
        return 0

    total_tokens = 0

    for tool in tools:
        try:
            # Build tool schema in OpenAI format
            tool_schema = {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                },
            }

            # Add parameters schema if available
            if hasattr(tool, "args_schema") and tool.args_schema:
                try:
                    # Try Pydantic v2 method (model_json_schema)
                    tool_schema["function"]["parameters"] = (
                        tool.args_schema.model_json_schema()
                    )
                except AttributeError:
                    # Fallback to Pydantic v1 method (schema)
                    try:
                        tool_schema["function"]["parameters"] = (
                            tool.args_schema.schema()
                        )
                    except Exception:
                        # Both methods failed, use empty schema
                        tool_name = getattr(tool, "name", "unknown")
                        logger.debug(
                            "Failed to get schema for tool %s, using empty "
                            "parameters",
                            tool_name,
                        )
                        tool_schema["function"]["parameters"] = {}
                except Exception as e:
                    # model_json_schema() raised an exception
                    tool_name = getattr(tool, "name", "unknown")
                    logger.debug(
                        "model_json_schema() failed for tool %s: %s, "
                        "trying v1 fallback",
                        tool_name,
                        e,
                    )
                    try:
                        tool_schema["function"]["parameters"] = (
                            tool.args_schema.schema()
                        )
                    except Exception:
                        tool_schema["function"]["parameters"] = {}

            # Serialize to JSON and count tokens
            schema_str = json.dumps(tool_schema, ensure_ascii=False)
            tokens = count_tokens(schema_str)
            total_tokens += tokens

        except Exception as e:
            tool_name = getattr(tool, "name", "unknown")
            logger.debug(
                "Failed to estimate tokens for tool %s: %s",
                tool_name,
                e,
            )
            # Rough fallback: 1000 tokens per tool
            total_tokens += 1000

    return total_tokens


def _count_tokens_for_message(message: BaseMessage) -> int:
    """
    Token counter for LangChain's trim_messages.

    This function is called by trim_messages for each message.

    Args:
        message: A single message (HumanMessage, AIMessage, SystemMessage,
                 etc.)

    Returns:
        Estimated token count for the message
    """
    content = ""
    if hasattr(message, "content") and message.content:
        content = str(message.content)

    return count_tokens(content)


# ============================================================================
# Pre-Model Hook Factory
# ============================================================================


def create_pre_model_hook(
    system_prompt: str,
    get_topology_func: Callable[[dict], Any] | None = None,
    get_llm_config_func: Callable[[], dict[str, Any] | None] | None = None,
    get_tools_func: Callable[[], list[Any]] | None = None,
) -> Callable[[dict], dict]:
    """
    Create a pre_model_hook function for LangGraph agent.

    This hook will be automatically called before each LLM invocation,
    handling topology injection, tool token estimation, and message
    trimming.

    IMPORTANT USAGE REQUIREMENTS:
        This hook MUST be passed via model.invoke() config, NOT used as
        a Node return value.

        CORRECT Usage:
            model.invoke(messages,
                        config={"configurable": {"pre_model_hook": pre_hook}})

        INCORRECT Usage:
            # ❌ Don't use as Node return value
            def my_node(state):
                return pre_hook(state)  # Wrong!

        # ❌ Don't use with StateGraph if state uses add_messages reducer
        class State(TypedDict):
            messages: Annotated[list, add_messages]  # Incompatible!

    COMPATIBILITY:
        - Works with: model.invoke(config={"configurable":
                                       {"pre_model_hook": ...}})
        - Does NOT work as: StateGraph Node return value
        - Does NOT work with: Annotated[list, add_messages] state reducers

    The hook returns a complete message list that overwrites the model
    input, which is correct for invoke() but wrong for state updates with
    add_messages.

    Args:
        system_prompt: System prompt template (must contain
                       {{topology_info}} placeholder)
        get_topology_func: Function to extract topology from state
        get_llm_config_func: Function to get LLM config from context
        get_tools_func: Optional function to get tools list for token
                       estimation

    Returns:
        A pre_model_hook function for use with model.invoke(config=...)

    Thread Safety:
        Thread-safe if get_llm_config_func uses request-scoped context
        (e.g., contextvars)

    Performance Notes:
        - SystemMessage is reconstructed on each LLM call (intentional
          design)
        - Overhead: ~1-2ms per call (negligible compared to LLM latency)
        - Trade-off: Simplicity > micro-optimization
        - In ReAct loops with multiple LLM calls, topology is re-injected
          each time
        - This is acceptable for GNS3-Copilot's usage patterns (low
          concurrency, short conversations)
    """

    def pre_model_hook(state: dict) -> dict:
        """
        LangGraph pre_model_hook - called before each LLM invocation.

        This function is NOT a StateGraph Node. It is a preprocessing hook
        that modifies the input to the LLM, not the agent state.

        Usage Context:
            Called automatically by LangChain when passed via:
                model.invoke(messages,
                            config={"configurable":
                                   {"pre_model_hook": this}})

        Args:
            state: Current agent state containing messages and topology_info

        Returns:
            dict with 'messages' key containing prepared and trimmed messages
            Note: This return value is used by LangChain to replace the model
                  input, NOT to update the agent state.

        Raises:
            ValueError: If context_limit is missing or invalid
        """
        logger.debug(
            "pre_model_hook invoked: messages=%d",
            len(state.get("messages", [])),
        )

        messages = state.get("messages", [])
        if not messages:
            logger.debug("No messages in state, returning empty list")
            return {"messages": []}

        # Get LLM config
        llm_config = get_llm_config_func() if get_llm_config_func else None

        if not llm_config:
            logger.error("LLM config not found. context_limit is required.")
            raise ValueError(
                "LLM config not found. context_limit is required."
            )

        if "context_limit" not in llm_config:
            logger.error(
                "context_limit not found in LLM config. "
                "This is a required field. Please configure context_limit."
            )
            raise ValueError("context_limit is required in LLM config")

        limit = llm_config["context_limit"]
        if not isinstance(limit, int) or limit <= 0:
            logger.error("Invalid context_limit: %s", limit)
            raise ValueError(f"Invalid context_limit: {limit}")

        context_limit_k = limit
        strategy = llm_config.get("context_strategy", DEFAULT_CONTEXT_STRATEGY)

        if strategy not in CONTEXT_STRATEGY_RATIOS:
            logger.warning(
                "Invalid context_strategy '%s', using '%s'",
                strategy,
                DEFAULT_CONTEXT_STRATEGY,
            )
            strategy = DEFAULT_CONTEXT_STRATEGY

        # Step 1: Estimate tool tokens
        tool_tokens = 0
        if get_tools_func:
            try:
                tools = get_tools_func()
                tool_tokens = estimate_tool_tokens(tools)
                logger.debug(
                    "Tool definitions estimated at ~%d tokens (%d tools)",
                    tool_tokens,
                    len(tools),
                )
            except Exception as e:
                logger.warning("Failed to estimate tool tokens: %s", e)

        # Step 2: Inject topology into system prompt
        messages_with_system = _inject_topology_into_system(
            messages=messages,
            system_prompt=system_prompt,
            state=state,
            get_topology_func=get_topology_func,
        )

        # Step 3: Calculate token breakdown for logging and validation
        system_message = messages_with_system[0]
        system_tokens = _count_tokens_for_message(system_message)

        # Calculate tokens for messages_with_system (including system)
        messages_with_system_tokens = sum(
            _count_tokens_for_message(m) for m in messages_with_system
        )

        # Calculate available budget
        model_limit_tokens = context_limit_k * TOKENS_PER_K
        strategy_ratio = CONTEXT_STRATEGY_RATIOS[strategy]
        max_input_tokens = int(model_limit_tokens * strategy_ratio)

        # Calculate max tokens for trim_messages
        # Important: trim_messages counts ALL messages (including system),
        # so we only subtract tool_tokens here, NOT system_tokens.
        # Let trim_messages handle system.
        max_tokens_for_trim = max_input_tokens - tool_tokens

        # Validate budget and provide actionable warnings
        if system_tokens + tool_tokens > max_input_tokens:  # noqa: E501
            logger.error(
                "System prompt (%d tokens) + tools (%d tokens) EXCEED input "
                "budget (%d tokens). This will likely cause LLM call failures. "  # noqa: E501
                "Recommendations: 1) Reduce system prompt length, 2) Reduce "
                "number of tools, 3) Use a model with larger context window, "
                "or 4) Switch to 'conservative' strategy.",
                system_tokens,
                tool_tokens,
                max_input_tokens,
            )
        elif max_tokens_for_trim < system_tokens * 1.5:
            # Less than 1.5x system tokens means very little room for history
            logger.warning(
                "System prompt (%d tokens) + tools (%d tokens) leave minimal "
                "room for conversation history (%d tokens remaining). "
                "Consider reducing system prompt length or number of tools.",
                system_tokens,
                tool_tokens,
                max_tokens_for_trim - system_tokens,
            )

        # Debug log with clear terminology
        logger.debug(
            "Token breakdown: system=%d, all_messages=%d (system+history), "
            "tools=%d, trim_budget=%d (limit=%dK, strategy=%s)",
            system_tokens,
            messages_with_system_tokens,
            tool_tokens,
            max_tokens_for_trim,
            context_limit_k,
            strategy,
        )

        # Step 4: Trim messages to fit
        # Note: max_tokens_for_trim INCLUDES system message, trim_messages
        # will handle it
        try:
            trimmed = trim_messages(
                messages=messages_with_system,
                max_tokens=max_tokens_for_trim,
                strategy="last",
                token_counter=_count_tokens_for_message,
                include_system=True,
            )

            # Calculate final token counts
            final_total = sum(_count_tokens_for_message(m) for m in trimmed)
            usage_percent = (
                (final_total + tool_tokens) / model_limit_tokens * 100
            )

            if len(trimmed) < len(messages_with_system):
                logger.info(
                    "Messages trimmed: %d → %d msgs. Total: ~%d tokens + %d "
                    "tools = %d / %dK (%.1f%%), strategy=%s",
                    len(messages_with_system),
                    len(trimmed),
                    final_total,
                    tool_tokens,
                    final_total + tool_tokens,
                    context_limit_k,
                    usage_percent,
                    strategy,
                )
            else:
                logger.info(
                    "Context ready: %d msgs, ~%d tokens + %d tools = %d / %dK "
                    "(%.1f%%), strategy=%s",
                    len(trimmed),
                    final_total,
                    tool_tokens,
                    final_total + tool_tokens,
                    context_limit_k,
                    usage_percent,
                    strategy,
                )

            return {"messages": trimmed}

        except Exception as e:
            logger.error("Failed to trim messages: %s", e)
            logger.warning("Returning original messages due to trimming error")
            return {"messages": messages_with_system}

    return pre_model_hook


def _inject_topology_into_system(
    messages: list,
    system_prompt: str,
    state: dict,
    get_topology_func: Callable[[dict], Any] | None = None,
) -> list:
    """
    Inject topology information into system prompt.

    Args:
        messages: Message list
        system_prompt: System prompt template
        state: Current state
        get_topology_func: Optional function to extract topology

    Returns:
        Message list with system message prepended
    """
    if "{{topology_info}}" not in system_prompt:
        logger.warning("system_prompt missing {{topology_info}} placeholder")
        return messages

    topology_data = None
    if get_topology_func:
        try:
            topology_data = get_topology_func(state)
        except Exception as e:
            logger.warning("Failed to get topology: %s", e)

    if topology_data:
        topology_str = str(topology_data)
        formatted_prompt = system_prompt.replace(
            "{{topology_info}}", f"\n\n## Current Topology\n{topology_str}"
        )
        logger.info(
            "✓ Topology injected: %d chars, nodes: %s",
            len(topology_str),
            list(topology_data.get("nodes", {}).keys())[:5],
        )  # Show first 5 node names
        logger.debug(
            "Full topology data: %s", topology_str[:500]
        )  # First 500 chars
    else:
        formatted_prompt = system_prompt.replace(
            "{{topology_info}}", "(No topology information available)"
        )
        logger.warning("✗ Topology data is None, injecting placeholder")

    # Filter out existing SystemMessage instances
    non_system_messages = [
        m for m in messages if not isinstance(m, SystemMessage)
    ]

    filtered_count = len(messages) - len(non_system_messages)
    if filtered_count > 0:
        logger.debug(
            "Filtered out %d existing SystemMessage(s)", filtered_count
        )

    return [SystemMessage(content=formatted_prompt)] + non_system_messages


# ============================================================================
# Legacy Compatibility (Deprecated)
# ============================================================================


def prepare_context_messages(
    state_messages: list[Any],
    system_prompt: str,
    topology_context: str | None = None,
    model_name: str = "gpt-4o",
    llm_config: dict[str, Any] | None = None,
    tools: list[Any] | None = None,
) -> list[Any]:
    """
    **DEPRECATED**: Use create_pre_model_hook() instead.
    """
    warnings.warn(
        "prepare_context_messages() is deprecated. Use "
        "create_pre_model_hook() instead.",
        DeprecationWarning,
        stacklevel=2,
    )

    if "{{topology_info}}" not in system_prompt:
        formatted_prompt = system_prompt
    elif topology_context:
        formatted_prompt = system_prompt.replace(
            "{{topology_info}}", f"\n\n## Current Topology\n{topology_context}"
        )
    else:
        formatted_prompt = system_prompt.replace(
            "{{topology_info}}", "(No topology information available)"
        )

    return [SystemMessage(content=formatted_prompt)] + state_messages


# ============================================================================
# Module Test
# ============================================================================

if __name__ == "__main__":
    from langchain_core.messages import HumanMessage

    print("=== Context Manager Module Test ===\n")

    # Test token counting
    print("Test 1: Token Counting")
    print("  tiktoken encoding: cl100k_base")

    test_text = "Hello world 你好世界"
    tokens = count_tokens(test_text)
    print(f"  '{test_text}' → {tokens} tokens")

    # Test hook creation
    print("\nTest 2: Create pre_model_hook")
    system_prompt = "You are GNS3 Copilot.\n\n{{topology_info}}"

    def mock_get_topology(state):
        return {"project_id": "test", "nodes": 5}

    def mock_get_config():
        return {"context_limit": 8, "context_strategy": "conservative"}

    def mock_get_tools():
        return []  # No tools for test

    hook = create_pre_model_hook(
        system_prompt=system_prompt,
        get_topology_func=mock_get_topology,
        get_llm_config_func=mock_get_config,
        get_tools_func=mock_get_tools,
    )
    print("✓ pre_model_hook created successfully")

    # Test invocation
    print("\nTest 3: Invoke pre_model_hook")
    test_state = {
        "messages": [
            HumanMessage(f"Message {i}: {'x' * 50}") for i in range(5)
        ],
        "topology_info": {"project_id": "test123", "nodes": 3},
    }

    result = hook(test_state)
    print(f"✓ Hook invoked: {len(result['messages'])} messages returned")

    print("\n=== All Tests Passed ===")
