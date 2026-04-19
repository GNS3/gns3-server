<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This documentation is organized by AI with reference to actual code. AI can make mistakes — please verify against the source code when in doubt.


# LLM Context Window Management Implementation Document

## Overview

This document explains the context window management implementation mechanism for GNS3 Copilot, including message trimming, token counting, and configuration validation.

## Implementation Architecture

### 1. Core Modules

**File Location**: `gns3server/agent/gns3_copilot/agent/context_manager.py`

#### Token Counting Strategy

The system uses **tiktoken** for token counting (context_manager.py:60):

```python
_tiktoken_encoding = tiktoken.get_encoding("cl100k_base")
```

**Required Dependency**:
```bash
pip install tiktoken>=0.8.0
```

If tiktoken is not installed, the system will throw a `ModuleNotFoundError` at startup.

#### Key Functions

**`count_tokens(text: str) -> int`** (context_manager.py:84-100)
- Uses tiktoken to accurately count tokens in text
- Uses `cl100k_base` encoding
- Returns the exact token count

**`estimate_tool_tokens(tools: list) -> int`** (context_manager.py:103-169)
- Serializes tool schema to JSON
- Uses tiktoken to count token consumption of tool definitions
- Supports Pydantic v1/v2 compatibility
- Falls back to 1000 tokens on failure

**`create_pre_model_hook(...)`** (context_manager.py:195-402)
- Creates a preprocessing function (pre_model_hook)
- Automatically executes before each LLM call:
  1. Injects topology information into system prompt
  2. Estimates token consumption of tool definitions
  3. Trims message history to fit context limits
- Returns a callable function for preparing messages

### 2. Detailed Trimming Logic

#### 2.1 Token Budget Allocation

When calling the LLM, the content sent consists of two parts:

```
Complete request sent to LLM:
┌─────────────────────────────────────────────────────────────┐
│ 1. Messages (managed by us)                                  │
│    ├─ SystemMessage: system prompt + topology (template injection) │
│    └─ HumanMessage/AIMessage: user messages / history messages │
├─────────────────────────────────────────────────────────────┤
│ 2. Tool Definitions (LangChain adds automatically, not in messages) │
│    ├─ Tool 1 schema (name, description, parameters)        │
│    ├─ Tool 2 schema                                        │
│    └─ ... (about 500-1500 tokens per tool)                │
└─────────────────────────────────────────────────────────────┘
```

**System Message Structure**:
- Uses template variable `{{topology_info}}` to dynamically inject topology
- System prompt contains placeholder: `"### CURRENT TOPOLOGY\n{{topology_info}}"`
- If topology exists, replaces with actual content
- If no topology, replaces with `"(No topology information available)"`

#### 2.2 Trimming Process

```
Step 1: Calculate Input Budget
┌─────────────────────────────────────────────────────────────┐
│ context_limit: 128,000 tokens (128K)                        │
│ strategy: balanced (75%)                                    │
│                                                            │
│ Input budget = 128 × 1000 × 0.75 = 96,000 tokens          │
└─────────────────────────────────────────────────────────────┘
                            ↓
Step 2: Subtract Tool Definitions
┌─────────────────────────────────────────────────────────────┐
│ Input budget: 96,000 tokens                                │
│ Tool definitions: 1,725 tokens                             │
│                                                            │
│ Available for messages = 96,000 - 1,725 = 94,275 tokens   │
└─────────────────────────────────────────────────────────────┘
                            ↓
Step 3: trim_messages Processing
┌─────────────────────────────────────────────────────────────┐
│ Call LangChain's trim_messages:                            │
│ - max_tokens = 94,275 (includes system message)           │
│ - strategy = "last" (keep latest messages)                 │
│ - token_counter = tiktoken counting function              │
│ - include_system = True (always keep system)               │
│                                                            │
│ trim_messages will:                                        │
│ 1. Keep SystemMessage (system + topology)                 │
│ 2. Starting from latest messages, keep as much history     │
│ 3. When exceeding limit, discard oldest messages          │
└─────────────────────────────────────────────────────────────┘
```

#### 2.3 Trimming Priority

The system preserves content in the following priority order:

| Priority | Content | Description |
|----------|---------|-------------|
| 1️⃣ | System Message (system prompt + topology) | Never removed |
| 2️⃣ | Latest user message | Keep at least the last 1 |
| 3️⃣ | Old conversation history | Discarded in chronological order |

**Note**: System prompt and topology info are merged into one SystemMessage via template variable and cannot be separated.

#### 2.4 Edge Case Handling

| Scenario | Handling |
|----------|----------|
| System (including topology) > budget | Keep complete SystemMessage (cannot separate system and topology) |
| Tools > budget | ERROR log, suggest increasing context_limit or reducing tool count |
| All history trimmed | Keep last 1 user message |

**Important Notes**:
- When system + topology exceed available budget, **both are preserved**
- Cannot discard only topology while keeping system prompt (already merged)

### 3. Integration with GNS3 Copilot

**File Location**: `gns3server/agent/gns3_copilot/agent/gns3_copilot.py`

#### Implementation Method

**Key Point**: The system uses a **custom StateGraph**, not LangGraph's pre-built agent.

Therefore, `pre_model_hook` cannot be passed via `model.invoke(config={"configurable": {"pre_model_hook": ...}})`.

**Correct Usage**: **Directly call** the `pre_hook` function to prepare messages.

```python
def llm_call(state: dict, config: RunnableConfig | None = None):
    """LLM decides whether to call a tool or not."""

    # 1. Get topology information
    project_id = config["configurable"].get("project_id")
    topology_info = None
    if project_id:
        topology_tool = GNS3TopologyTool()
        topology = topology_tool._run(project_id=project_id)
        if topology and "error" not in topology:
            topology_info = topology

    # 2. Create pre_model_hook
    system_prompt = load_system_prompt()
    pre_hook = create_pre_model_hook(
        system_prompt=system_prompt,
        get_topology_func=lambda s: s.get("topology_info"),
        get_llm_config_func=get_current_llm_config,
        get_tools_func=lambda: tools,
    )

    # 3. Create model with tools
    model_with_tools = create_base_model_with_tools(tools, llm_config=llm_config)

    # 4. ⭐ Key: directly call pre_hook to prepare messages
    logger.info("Calling pre_hook to prepare %d messages", len(messages))
    prepared_state = pre_hook({"messages": messages, "topology_info": topology_info})
    prepared_messages = prepared_state["messages"]

    # 5. Use prepared messages to call LLM
    response = model_with_tools.invoke(prepared_messages)

    return {"messages": [response], ...}
```

#### Why Not Pass via Config?

LangGraph's `pre_model_hook` parameter only applies to **pre-built agents**, not custom StateGraphs.

| Agent Type | pre_model_hook Support |
|------------|------------------------|
| `create_react_agent` | ✅ Via `pre_model_hook` parameter |
| `chat_agent_executor` | ✅ Via `pre_model_hook` parameter |
| **Custom StateGraph** | ❌ **Not supported**, need to call directly |

Our implementation uses a custom StateGraph (`agent_builder = StateGraph(MessagesState)`), so we must call `pre_hook` directly.

### 4. Execution Flow

```
User sends message
     ↓
llm_call node is called
     ↓
Get project_id (from config["configurable"])
     ↓
Call GNS3TopologyTool._run(project_id) to get topology
     ↓
Store topology_info to state
     ↓
Create pre_model_hook (via create_pre_model_hook())
     ↓
[Key] Directly call pre_hook({"messages": messages, "topology_info": topology_info})
     ├─ 1. Inject topology into system prompt
     ├─ 2. Estimate tool definitions tokens
     ├─ 3. Call trim_messages() to trim messages
     └─ 4. Return prepared message list
     ↓
Call model.invoke() with prepared messages
     ↓
Return LLM response
```

---

## Strategy Implementation

### Context Strategy Ratios

**Definition** (context_manager.py:68-72):

```python
CONTEXT_STRATEGY_RATIOS = {
    "conservative": 0.60,
    "balanced": 0.75,
    "aggressive": 0.85,
}
```

**Default Value** (context_manager.py:74):
```python
DEFAULT_CONTEXT_STRATEGY = "balanced"
```

### Strategy Comparison

| Strategy | Input Ratio | Output Reserved | Calculation Formula |
|----------|-------------|-----------------|---------------------|
| Conservative | 60% | 40% | `context_limit × 1000 × 0.60` |
| Balanced | 75% | 25% | `context_limit × 1000 × 0.75` |
| Aggressive | 85% | 15% | `context_limit × 1000 × 0.85` |

---

## Log Output

### Normal Case (topology successfully injected)

```
INFO: Calling pre_hook to prepare 1 messages
INFO: ✓ Topology injected: 7722 chars, nodes: ['netshoot-1', 'R1', 'R2', 'IOU-L3-1', 'IOU-L3-2']
INFO: Context ready: 2 msgs, ~3815 tokens + 1725 tools = 5540 / 128K (4.3%), strategy=conservative
INFO: Messages prepared: 1 → 2
INFO: LLM call completed: tool_calls=0
```

### When Trimming Occurs

```
INFO: Calling pre_hook to prepare 50 messages
INFO: ✓ Topology injected: 8500 chars, nodes: ['R1', 'R2', ...]
INFO: Messages trimmed: 50 → 25 msgs. Total: ~82000 tokens + 1725 tools = 83725 / 128K (65.4%), strategy=balanced
INFO: Messages prepared: 50 → 25
```

### When topology is None

```
INFO: Calling pre_hook to prepare 1 messages
WARNING: ✗ Topology data is None, injecting placeholder
INFO: Context ready: 2 msgs, ~800 tokens + 1725 tools = 2525 / 128K (2.0%), strategy=balanced
```

---

## Error Handling

### tiktoken Not Installed

If tiktoken is not installed, the system will throw an error at startup:

```python
ModuleNotFoundError: No module named 'tiktoken'
```

**Solution**:
```bash
pip install tiktoken>=0.8.0
```

### context_limit Missing or Invalid

If there is no `context_limit` in the LLM configuration or the value is invalid (context_manager.py:285-295):

```python
if "context_limit" not in llm_config:
    raise ValueError("context_limit is required in LLM config")

limit = llm_config["context_limit"]
if not isinstance(limit, int) or limit <= 0:
    raise ValueError(f"Invalid context_limit: {limit}")
```

### Trimming Failure

```python
try:
    trimmed = trim_messages(...)
except Exception as e:
    logger.error("Failed to trim messages: %s", e)
    logger.warning("Returning original messages due to trimming error")
    return {"messages": messages_with_system}
```

---

## Related Source Files

- `gns3server/agent/gns3_copilot/agent/context_manager.py` - Context management core logic
- `gns3server/agent/gns3_copilot/agent/gns3_copilot.py` - LLM call node (StateGraph)
- `gns3server/agent/gns3_copilot/agent/model_factory.py` - Model creation and tool binding


