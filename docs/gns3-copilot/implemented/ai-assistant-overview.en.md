<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

# GNS3-Copilot AI Assistant Overview

## Overall Architecture

```mermaid
flowchart TB
    subgraph "Client"
        A["Web UI"] --> B["SSE Streaming"]
    end

    subgraph "FastAPI Route Layer"
        B --> C["POST /chat/stream\nPOST /chat/inject"]
        C --> D["Auth + LLM Config Loading\nSet ContextVars"]
    end

    subgraph "AgentService (Project-level)"
        D --> E["LangGraph Agent\nStateGraph"]
        E --> F["SQLite Checkpointer\ncopilot_checkpoints.db"]
    end

    subgraph "LangGraph Workflow"
        E --> G["llm_call node\nmodel invocation"]
        E --> H["tool_node\ntool execution"]
        E --> I["title_generator_node\nauto title"]
        E --> J["abort_handler_node\ninterrupt handling"]
    end

    subgraph "Three Copilot Modes"
        G --> K["teaching_assistant\ndiagnostic read-only"]
        G --> L["lab_automation_assistant\nfull control"]
        G --> M["troubleshooting_injection\nfault injection"]
    end

    subgraph "LLM Config System"
        D --> N["User configs\nGroup config inheritance\nAPI key encryption"]
    end
```

## API Endpoints

| Endpoint | Function |
|---|---|
| `POST /v3/projects/{pid}/chat/stream` | Streaming conversation (SSE), supports three copilot modes |
| `POST /v3/projects/{pid}/chat/inject` | Fault injection entry, auto-switches to `troubleshooting_injection` mode |
| `GET /v3/projects/{pid}/chat/sessions` | List sessions (supports filtering, pagination) |
| `DELETE /v3/projects/{pid}/chat/sessions/{sid}` | Delete session |
| `PATCH /v3/projects/{pid}/chat/sessions/{sid}` | Update session (rename, pin) |
| `POST /v3/projects/{pid}/chat/sessions/{sid}/abort` | Abort an active session |

## LangGraph Agent Workflow

```mermaid
sequenceDiagram
    participant U as User
    participant API as FastAPI
    participant AS as AgentService
    participant LLM as LLM Node
    participant Tool as Tool Node
    participant TGen as Title Node

    U->>API: send message
    API->>AS: stream_chat()
    AS->>AS: set ContextVars<br/>(jwt_token, llm_config)

    Note over AS,LLM: llm_call node
    AS->>LLM: invoke pre-compiled model
    LLM->>LLM: pre_model_hook<br/>inject topology + trim context
    LLM-->>AS: AI reply (may include tool_calls)

    opt has tool calls
        AS->>Tool: execute tools
        Tool-->>AS: tool results
        AS->>LLM: continue LLM call
    end

    opt first turn and no title
        AS->>TGen: auto-generate title
        TGen-->>AS: session title
    end

    AS-->>API: SSE streaming response
    API-->>U: stream output
```

## Three Copilot Modes

### Mode Comparison

| Mode | Tool Scope | Use Case |
|---|---|---|
| `teaching_assistant` (default) | Diagnostic read-only + packet analysis + node management | Teaching demos, troubleshooting guidance |
| `lab_automation_assistant` | All tools (including config changes) | Lab automation, device configuration |
| `troubleshooting_injection` | Fault injection tool set | Troubleshooting practice, fault simulation |

### Tool Binding Details

| Tool | teaching_assistant | lab_automation_assistant | troubleshooting_injection |
|---|---|---|---|
| `template_list` get templates | ✓ | ✓ | |
| `node_create` create nodes | ✓ | ✓ | |
| `link_create` create links (native) | ✓ | ✓ | |
| `node_start` start nodes | ✓ | ✓ | |
| `node_update` rename | ✓ | ✓ | |
| `node_stop` stop nodes | | ✓ | |
| `node_suspend` suspend nodes | | ✓ | |
| `device_show_run` read-only commands | ✓ | ✓ | ✓ |
| `device_config_send` config commands | | ✓ | ✓ |
| `vpcs_config_set` VPCS commands | | ✓ | |
| `packet_analysis` live packet analysis (native) | ✓ | ✓ | |
| `packet_analysis_skills` protocol knowledge (native) | ✓ | ✓ | |
| `device_skill_get` device skills | ✓ | ✓ | |
| `link_update` link filters | | | ✓ |
| `injection_skill_get` fault injection skills | | | ✓ |
| `gns3_topology_reader` topology info (native) | | | ✓ |

The mode is selected in the `llm_call` node via `copilot_mode`, which picks the corresponding tool list and binds it to the LLM model instance through `create_base_model_with_tools(mode_tools, llm_config)`.

## Context Window Management

```mermaid
flowchart LR
    A["LLM call triggered"] --> B["pre_model_hook"]
    B --> C["Inject topology\ninto System Prompt"]
    B --> D["Estimate tool definition\ntoken cost"]
    B --> E["trim_messages\nby strategy"]
    E --> F["conservative 60%\nbalanced 75%\naggressive 85%"]
    F --> G["Invoke LLM"]
```

- Accurate token counting via tiktoken (`cl100k_base`)
- Three trimming strategies: conservative / balanced / aggressive
- Auto-injects `{{topology_info}}` into System Prompt

## Session Management

- Per-project independent SQLite database (`gns3-copilot/copilot_checkpoints.db`)
- Supports pin, rename, delete, history query
- Auto-records token usage, message count, LLM call count

## LLM Config System

| Feature | Description |
|---|---|
| User-level configs | Each user can independently configure provider / model / api_key |
| Group inheritance | Users auto-inherit group config when no personal config is set |
| API key encryption | Auto-encrypted at database storage |
| Optimistic locking | `version` field prevents concurrent modification conflicts |

## Key Design Points

1. **Project-level Isolation** — Each GNS3 project has its own Agent instance and SQLite storage
2. **ContextVars Safe Passing** — JWT token, API key exist only in memory, auto-cleared when request ends
3. **LangGraph StateGraph** — Custom nodes + conditional edges, supports ReAct loop and recursion limits
4. **SSE Streaming** — Real-time push of content / tool_call / tool_start / tool_end / error / done events
5. **Hot Reload** — System Prompt, Skills, Protocols all support runtime reload
6. **Mode-based Tool Sets** — Three copilot modes bind different tools, safely isolated by scenario
