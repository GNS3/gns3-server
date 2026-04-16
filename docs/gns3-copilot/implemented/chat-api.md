<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

# GNS3 Copilot Agent Chat API Design Document

## Overview

This document describes the architectural design and implementation plan for the GNS3 Copilot Chat API. This API enables clients to interact with the GNS3 Copilot Agent through a RESTful interface, providing streaming conversations, session management, and project topology queries.

## Core Features

- **Project-level Isolation**: Each GNS3 project has its own Agent instance and session storage
- **Streaming Responses**: Uses Server-Sent Events (SSE) for real-time streaming output
- **Session Management**: Supports session listing, renaming, deletion, and history queries
- **Statistics Tracking**: Automatically records message counts, LLM call counts, and token usage
- **User Isolation**: Each user has independent LLM configurations and session spaces

## Architecture Design

### Overall Architecture

```
Frontend (Web UI)
    │
    │ SSE Streaming
    ▼
FastAPI Chat API Routes
    │
    │ Project-level Agent Management
    ▼
AgentService (per project)
    │
    ├─ SQLite Checkpointer (project_dir/gns3-copilot/)
    │   ├─ checkpoints table (LangGraph state)
    │   └─ chat_sessions table (session metadata)
    │
    └─ LangGraph Agent
        ├─ llm_call node
        ├─ should_continue node
        └─ tool_node (GNS3 tools)
```

### Project-level Checkpoint Design

Each GNS3 project creates a `gns3-copilot/copilot_checkpoints.db` SQLite database in the project directory, containing two tables:

1. **checkpoints table** (managed by LangGraph): stores Agent conversation state and memory
2. **chat_sessions table** (custom): stores session metadata and statistics

**Directory Structure**:
```
{project.path}/
├── gns3-copilot/
│   └── copilot_checkpoints.db
├── project-files/
└── project.gns3
```

**Design Advantages**:
- All related data is automatically cleaned up when the project is deleted
- Achieves project-level session isolation
- Facilitates backup and migration

## User Authentication Information Passing

### Background Requirements

GNS3 Copilot Agent requires the following information to work properly:
1. **user_id**: Get user-specific LLM configuration
2. **jwt_token**: Authenticate when calling GNS3 API
3. **llm_config**: Contains provider, model, api_key, etc.

### ContextVars Solution

Uses Python's `contextvars.ContextVar` to pass data within request scope, avoiding persisting sensitive information to checkpoint.

**Data Flow**:
```
1. API layer gets user information
   ├─ Get user_id from FastAPI get_current_active_user
   ├─ Extract jwt_token from Authorization header
   └─ Query LLM configuration from database (API key already decrypted)

2. Set ContextVars (temporary in-memory storage)
   ├─ set_current_jwt_token(jwt_token)
   └─ set_current_llm_config(llm_config)

3. Build secure LangGraph config (only contains non-sensitive identifiers)
   {
     "configurable": {
       "thread_id": session_id,
       "project_id": project_id
     },
     "metadata": {
       "user_id": user_id
     }
   }

4. LLM node gets configuration from ContextVars
   ├─ get_current_jwt_token()
   └─ get_current_llm_config()
```

**Solution Advantages**:
- Sensitive data (JWT token, API key) only stored in memory
- Automatically cleared after request ends, not persisted to database
- Avoids serialization/deserialization overhead
- Achieves request-level data isolation

## Session Management

### chat_sessions Table Structure

| Field | Type | Description |
|-------|------|-------------|
| id | INTEGER | Primary key (auto-increment) |
| thread_id | TEXT | LangGraph thread_id (unique) |
| user_id | TEXT | User ID |
| project_id | TEXT | GNS3 project ID |
| title | TEXT | Session title |
| message_count | INTEGER | Number of messages |
| llm_calls_count | INTEGER | Number of LLM calls |
| input_tokens | INTEGER | Total input tokens |
| output_tokens | INTEGER | Total output tokens |
| total_tokens | INTEGER | Total tokens |
| last_message_at | TIMESTAMP | Last message time |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Update time |
| metadata | TEXT | Reserved metadata (JSON) |
| stats | TEXT | Additional statistics (JSON) |
| pinned | BOOLEAN | Whether pinned (default FALSE) |

**Indexes**:
- `idx_thread_id`: thread_id unique index
- `idx_user_project`: user_id + project_id composite index
- `idx_pinned_updated`: pinned + updated_at composite index (for pin sorting)

### Database Migration

**Implementation Location**: `_create_chat_sessions_table` method in `agent_service.py`

**Migration Strategy**:
- Use `PRAGMA table_info(chat_sessions)` to check if columns exist
- If `pinned` column doesn't exist, execute `ALTER TABLE ADD COLUMN` to add it
- Ensure column exists before creating index

**Code Example**:
```python
# Check if pinned column exists, add it if not (migration for existing databases)
cursor = await conn.execute("PRAGMA table_info(chat_sessions)")
columns = await cursor.fetchall()
column_names = [col[1] for col in columns]

if "pinned" not in column_names:
    log.debug("Adding pinned column to existing chat_sessions table")
    await conn.execute("ALTER TABLE chat_sessions ADD COLUMN pinned BOOLEAN DEFAULT FALSE")
    await conn.commit()

# Create pinned index (after column is guaranteed to exist)
await conn.execute("CREATE INDEX IF NOT EXISTS idx_pinned_updated ON chat_sessions(pinned DESC, updated_at DESC)")
```

**Advantages**:
- Backward compatible: existing databases automatically upgraded without manual intervention
- Idempotent: repeated execution won't cause errors
- Zero downtime: migration happens automatically during initialization

### ChatSessionsRepository

Provides CRUD operations for sessions:

- **create_session**: Create new session
- **get_session_by_thread**: Query session by thread_id
- **list_sessions**: List user's sessions (supports filtering and pagination, sorted by pinned and updated_at)
- **update_session**: Update session (supports incremental counter updates)
- **delete_session**: Delete session and its checkpoints
- **delete_all_sessions**: Delete all sessions in project
- **pin_session**: Pin or unpin session

### Automatic Statistics Collection

Statistics are collected in real-time during conversation, and updated to `chat_sessions` table in one batch after streaming ends.

**Implementation Location**: `stream_chat` method in `agent_service.py`

**Statistics Logic**:

1. **message_count (number of messages)**
   - Initial value: 1 (user message)
   - `on_chat_model_end` event: +1 (AI complete reply, not each chunk)
   - `on_tool_end` event: +1 (each tool execution result)

2. **llm_calls_count (number of LLM calls)**
   - Listen to `on_chat_model_start` event
   - +1 each time LLM starts generation

3. **input_tokens (input tokens)**
   - Extracted from `usage_metadata` in `on_chat_model_end` event
   - **Important**: input_tokens returned by LangGraph already includes conversation history, accumulates previous conversation content on each LLM call
   - Example: 1st call input=8674, 2nd call input=9421 (includes 1st conversation 8674+675+system prompt increment)

4. **output_tokens (output tokens)**
   - Extracted from `usage_metadata` in `on_chat_model_end` event
   - **Important**: output_tokens returned by LangGraph is also accumulated value, includes output from all LLM calls
   - Example: 1st actual output=675, 2nd actual output=9, accumulated output=684 (675+9)

5. **total_tokens (total tokens)**
   - Calculation formula: input_tokens + output_tokens
   - Take the accumulated value from the last LLM call for calculation

**Statistics Example** (real data):
- 1st LLM call (AI reply): input=8674, output=675
- 2nd LLM call (generate title): input=9421, output=684 (accumulated value: 675+9)
- Final storage: input_tokens=9421, output_tokens=684, total_tokens=10105
- Note: LangGraph automatically accumulates, code can directly take the last value

**Notes**:
- message_count counts **complete messages**, not streaming chunks
- Token data depends on LLM's returned `usage_metadata`, some models may not support
- Statistics are incrementally updated to database via `update_session` method after stream ends
- LangGraph automatically handles input and output history accumulation, code uses the last LLM call value
- **Message ID handling**: Assign ID when creating initial message (`HumanMessage(id=str(uuid4()))`), messages read from checkpoint without ID are also automatically generated
- **Format conversion**: Use `message_converters.py` module to handle conversion between LangChain and OpenAI formats, ensuring tool_calls format conforms to OpenAI specification

### Automatic Title Synchronization

Session title is automatically generated by `title_generator_node` node, saved in `conversation_title` field in LangGraph checkpoint.

**Synchronization Mechanism**:
1. After streaming Chat completes, read final state from checkpoint
2. Check if `conversation_title` has changed
3. If changed, update to `chat_sessions` table

**Advantages**:
- Avoids accessing database directly in nodes (prevents circular dependencies)
- All database updates concentrated after stream ends
- Clear logic, easy to maintain

## SSE Message Format

Chat API uses Server-Sent Events (SSE) for streaming transmission.

### Message Types

| type | Description | Included Fields |
|------|-------------|------------------|
| content | AI text content (streaming) | content, message_id (optional) |
| tool_call | LLM decides to call tool (streaming, parameters accumulated gradually) | tool_call (object, includes id, type, function), session_id, message_id (optional) |
| tool_start | Tool starts execution | tool_name, tool_call_id, session_id |
| tool_end | Tool execution complete | tool_name, tool_output, session_id |
| error | Error message | error, session_id |
| done | Stream end | session_id |

**Tool Output Format** (`tool_output` field):
- If the tool returns a non-string type (dict, list), it is automatically serialized to JSON format using `json.dumps(obj, ensure_ascii=False, indent=2)`
- If the tool returns a string type, it is passed through as-is
- This ensures all structured data is in standard JSON format, making it easy for the frontend to parse with `JSON.parse()`
- Chinese and other non-ASCII characters are preserved (not escaped to `\uXXXX`)

| heartbeat | Heartbeat keepalive | session_id |

### Message Examples

```json
// AI text streaming output
{"type": "content", "content": "Hello! How can I help"}

// LLM decides to call tool (streaming transmission, parameters accumulated gradually)

// 1st chunk: tool call starts (parameters empty)
{
  "type": "tool_call",
  "tool_call": {
    "id": "call_123",
    "type": "function",
    "function": {"name": "execute_multiple_device_commands", "arguments": ""}
  },
  "session_id": "xxx"
}

// 2nd chunk: parameters accumulating
{
  "type": "tool_call",
  "tool_call": {
    "id": "call_123",
    "type": "function",
    "function": {"name": "execute_multiple_device_commands", "arguments": "{\"device_names\": [\"R1\"], "}
  },
  "session_id": "xxx"
}

// 3rd chunk: parameters accumulating
{
  "type": "tool_call",
  "tool_call": {
    "id": "call_123",
    "type": "function",
    "function": {"name": "execute_multiple_device_commands", "arguments": "{\"device_names\": [\"R1\"], \"commands\": [\"show ver\"]}"}
  },
  "session_id": "xxx"
}

// 4th chunk: parameters complete (mark complete=true)
{
  "type": "tool_call",
  "tool_call": {
    "id": "call_123",
    "type": "function",
    "function": {
      "name": "execute_multiple_device_commands",
      "arguments": "{\"device_names\": [\"R1\"], \"commands\": [\"show ver\"]}",
      "complete": true
    }
  },
  "session_id": "xxx"
}

// Tool starts execution (associated via tool_call_id)
{
  "type": "tool_start",
  "tool_name": "execute_multiple_device_commands",
  "tool_call_id": "call_123",
  "session_id": "xxx"
}

// Tool execution complete
{
  "type": "tool_end",
  "tool_name": "execute_multiple_device_commands",
  "tool_output": "[\n  {\n    \"device_name\": \"R-1\",\n    \"status\": \"success\",\n    \"output\": \"Cisco IOS Software, \\n   IOSv Software (X86_64_LINUX_IOSD-UNIVERSALK9-M), Version 15.2(1.90)\"\n  },\n  {\n    \"device_name\": \"R-2\",\n    \"status\": \"failed\",\n    \"error\": \"Connection timeout\"\n  }\n]",
  "session_id": "xxx"
}

// Stream end
{"type": "done", "session_id": "xxx"}

// Error
{"type": "error", "error": "Project not found", "session_id": "xxx"}
```

### Streaming Tool Call Mechanism

**Background**: When LLM generates tool call parameters, it outputs character by character like text content.

**Implementation**: Use `ToolCallStreamAccumulator` class to maintain state, handling three phases:

1. **Initialization Phase**: Get tool ID and name from `tool_calls`, send initial `tool_call` event (parameters empty)

2. **Accumulation Phase**: Get parameter fragments from `tool_call_chunks`, accumulate complete parameters via string concatenation, send updated `tool_call` event after each accumulation

3. **Completion Phase**: Detect `finish_reason == "tool_calls"` or `"stop"`, send final `tool_call` event (mark `complete: true`)

**Frontend Handling**:
- When receiving `tool_call` event, determine if it's a new tool call based on `tool_call.id`
- Subsequent events with same ID are used to update parameter display
- When `function.complete: true`, parameters are complete, tool can be executed
- `tool_start` event contains `tool_call_id`, can associate with previous `tool_call` event

**Example Code** (frontend):
```javascript
// Maintain current tool call state
let currentToolCall = null;

function handleToolCallEvent(chunk) {
  const toolCall = chunk.tool_call;

  if (!currentToolCall || currentToolCall.id !== toolCall.id) {
    // New tool call
    currentToolCall = {
      id: toolCall.id,
      name: toolCall.function.name,
      arguments: toolCall.function.arguments,
      complete: toolCall.function.complete || false
    };
    displayToolCallStarted(currentToolCall);
  } else {
    // Update existing tool call parameters
    currentToolCall.arguments = toolCall.function.arguments;
    currentToolCall.complete = toolCall.function.complete || false;
    updateToolCallArguments(currentToolCall);
  }

  if (currentToolCall.complete) {
    // Parameters complete, ready to execute tool
    displayToolCallReady(currentToolCall);
  }
}
```

### Heartbeat Mechanism

**Purpose**: Prevent proxy server/load balancer from disconnecting SSE connection due to timeout.

**Implementation**: Use `asyncio.wait` to set timeout, send `heartbeat` message after timeout, then continue waiting for next event.

**Frontend Handling**: When receiving `heartbeat` message, ignore it directly, don't render anything.

## API Endpoints

All endpoints are under `/v3/projects/{project_id}/chat/` path.

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/stream` | Streaming Chat (main interface) |
| GET | `/sessions` | List sessions (sorted by pin and update time) |
| GET | `/sessions/{session_id}/history` | Get session history |
| PATCH | `/sessions/{session_id}` | Rename session |
| DELETE | `/sessions/{session_id}` | Delete session |
| PUT | `/sessions/{session_id}/pin` | Pin session |
| DELETE | `/sessions/{session_id}/pin` | Unpin session |

### POST /v3/projects/{project_id}/chat/stream

**Function**: Streaming conversation interface

**Request Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| message | string | Yes | User message content |
| session_id | string | No | Session ID (creates new session if not provided) |
| stream | boolean | No | Enable streaming response (default true) |
| temperature | float | No | LLM temperature (reserved, currently unused) |
| mode | string | No | Interaction mode (fixed as "text", reserved for future expansion) |

**Request Example**:
```json
// First message (new session)
{
  "message": "Hello, can you help me?",
  "stream": true
}

// Subsequent messages (continue session)
{
  "message": "Show me the network topology",
  "session_id": "d7e76375-6960-419a-9367-211ef64af877",
  "stream": true
}
```

**Response**: SSE stream, contains multiple types of messages (see message format section)

**Session ID Management**:
- **First message**: Do not send `session_id` in request, backend generates a new UUID
- **Retrieve session_id**: Each SSE message (including `done` message) contains `session_id` field
- **Subsequent messages**: Include the saved `session_id` in request body to continue conversation
- **Example flow**:
  1. First request: `{"message": "hello", "stream": true}` → generates new session
  2. Get `session_id` from SSE response: `{"type": "done", "session_id": "xxx-xxx-xxx"}`
  3. Second request: `{"message": "how are you?", "session_id": "xxx-xxx-xxx", "stream": true}`

**Project Status Check**: Only allows conversation when project status is "opened"

**Response Example** (SSE stream):
```
data: {"type": "content", "content": "Hello", "session_id": "d7e76375-6960-419a-9367-211ef64af877"}

data: {"type": "content", "content": "! I can help", "session_id": "d7e76375-6960-419a-9367-211ef64af877"}

data: {"type": "done", "session_id": "d7e76375-6960-419a-9367-211ef64af877"}
```

### GET /v3/projects/{project_id}/chat/sessions

**Function**: List all sessions in a project

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| user_id | string | No | Filter by user ID |
| limit | int | No | Maximum number of sessions (default 100) |

**Response**: Session list, includes statistics (message count, token usage, etc.), sorted by pin status and update time

**Response Example**:
```json
[
  {
    "id": 1,
    "thread_id": "d7e76375-6960-419a-9367-211ef64af877",
    "user_id": "admin",
    "project_id": "a0f46d81-e564-443c-b321-2cdebe80e321",
    "title": "GNS3 Topology Assistance",
    "message_count": 4,
    "llm_calls_count": 2,
    "input_tokens": 8500,
    "output_tokens": 1200,
    "total_tokens": 9700,
    "last_message_at": "2026-03-08T01:34:07",
    "created_at": "2026-03-07T17:48:07",
    "updated_at": "2026-03-08T01:34:07",
    "metadata": {},
    "stats": {},
    "pinned": false
  }
]
```

### GET /v3/projects/{project_id}/chat/sessions/{session_id}/history

**Function**: Get complete history of a session

**Path Parameters**:
- session_id: Session ID

**Query Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| limit | int | No | Maximum number of messages (default 100) |

**Response Example**:
```json
{
  "thread_id": "d7e76375-6960-419a-9367-211ef64af877",
  "title": "GNS3 Topology Assistance",
  "messages": [
    {
      "id": "f0247568-071d-412f-9e3e-4cbe815834ea",
      "role": "user",
      "content": "你能干点啥。",
      "metadata": {
        "created_at": "2026-03-07T17:48:07.848519"
      }
    },
    {
      "id": "lc_run--019cc969-eb81-7dd1-a894-e819daf81cd0",
      "role": "assistant",
      "content": "我可以作为GNS3网络实验的助教...",
      "tool_calls": [
        {
          "id": "call_00_xxx",
          "type": "function",
          "function": {
            "name": "get_gns3_topology",
            "arguments": {}
          }
        }
      ],
      "metadata": {}
    }
  ],
  "created_at": null,
  "updated_at": null,
  "llm_calls": 2
}
```

### PATCH /v3/projects/{project_id}/chat/sessions/{session_id}

**Function**: Rename session

**Request Parameters**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| title | string | Yes | New title (1-255 characters) |

**Request Example**:
```json
{
  "title": "New Session Title"
}
```

**Response**: Updated session information

### DELETE /v3/projects/{project_id}/chat/sessions/{session_id}

**Function**: Delete session and all its checkpoint data

**Response**: 204 No Content

### PUT /v3/projects/{project_id}/chat/sessions/{session_id}/pin

**Function**: Pin session to top of list

**Response Example**:
```json
{
  "id": 1,
  "thread_id": "d7e76375-6960-419a-9367-211ef64af877",
  "title": "GNS3 Topology Assistance",
  "pinned": true,
  ...
}
```

### DELETE /v3/projects/{project_id}/chat/sessions/{session_id}/pin

**Function**: Unpin session

**Response Example**:
```json
{
  "id": 1,
  "thread_id": "d7e76375-6960-419a-9367-211ef64af877",
  "title": "GNS3 Topology Assistance",
  "pinned": false,
  ...
}
```

**Sorting Rules**:
- Pinned sessions (pinned=true) appear at the front
- Among pinned sessions, sort by updated_at descending
- Normal sessions sort by updated_at descending

## Data Models

### ChatRequest

- message: str - User message content
- session_id: Optional[str] - Session ID (optional)
- stream: bool - Enable streaming response (default true)
- temperature: Optional[float] - LLM temperature parameter (Note: currently unused, reserved for future runtime override implementation. Current temperature is read from user's database LLM configuration)
- mode: Literal["text"] - Interaction mode

### ChatSession

Session model, stores session metadata and statistics.

**Base Fields**:
- id: Database auto-increment ID
- thread_id: LangGraph thread_id (session unique identifier)
- user_id: User ID
- project_id: GNS3 project ID
- title: Session title (auto-generated or user-modified)

**Statistics Fields**:
- message_count: Complete message count (user messages + AI replies + tool results)
- llm_calls_count: Total LLM call count
- input_tokens: Total input tokens (accumulated across all LLM calls)
- output_tokens: Total output tokens (accumulated across all LLM calls)
- total_tokens: Total tokens (input_tokens + output_tokens)

**Time Fields**:
- last_message_at: Timestamp of last message
- created_at: Session creation time
- updated_at: Session last update time

**Reserved Fields**:
- metadata: Metadata JSON string (stores mode, status, tags, etc.)
- stats: Additional statistics JSON string (stores tool call counts, etc.)

**Session Management**:
- pinned: Whether pinned to top of list (default false)

### ConversationHistory

- thread_id: str - Session ID
- title: str - Session title
- messages: List[OpenAIMessage] - Message list
- created_at: Optional[str] - Creation time
- updated_at: Optional[str] - Update time
- llm_calls: int - Number of LLM calls

### OpenAIMessage

OpenAI-compatible message model.

**Base Fields**:
- id: str - Message unique identifier (auto-generated or inherited from LangChain message)
- role: Literal["user", "assistant", "system", "tool"] - Message role
- content: str - Message content (supports text, JSON string)
- metadata: Optional[Dict] - Message metadata (includes created_at and other custom fields)
  - created_at: str - Message creation time (ISO 8601 format)
  - Other custom fields can be added as needed

**Tool-related Fields**:
- name: Optional[str] - Tool message name (tool message)
- tool_call_id: Optional[str] - Associated tool call ID (tool message)
- tool_calls: Optional[List[OpenAIToolCall]] - Tool call list (assistant message)
  - id: str - Tool call ID
  - type: Literal["function"] - Fixed as "function"
  - function: Dict - Contains name and arguments (dict or JSON string)

**Important Notes**:
- Message creation time is stored in `metadata.created_at` field
- Frontend should read `metadata.created_at` for message timestamp
- Historical messages may not have `created_at` in metadata (empty `{}`)

## Core Components

### Message Converters (Message Format Conversion)

**File**: `gns3server/agent/gns3_copilot/utils/message_converters.py`

**Responsibility**: Convert between LangChain message format and OpenAI-compatible format

**Main Functions**:
- `convert_langchain_to_openai()`: LangChain → OpenAI format
- `convert_openai_to_langchain()`: OpenAI → LangChain format
- `convert_stream_event_to_openai()`: Stream event → OpenAI SSE format

**Key Conversion Logic**:

1. **Message ID Handling**
   - Auto-generate UUID if message has no ID
   - Ensure all returned messages have unique identifier

2. **Metadata and Timestamp Handling**
   - Extract entire `metadata` dict from LangChain message
   - Message creation time stored in `metadata.created_at` field (ISO 8601 format)
   - No top-level `created_at` field in returned message
   - Frontend should read `message.metadata.created_at` for timestamp
   - Historical messages without metadata will have empty `{}`

3. **Tool Calls Format Conversion**
   - LangChain format: `{'name': 'xxx', 'args': {...}, 'id': 'yyy', 'type': 'tool_call'}`
   - OpenAI format: `{'id': 'yyy', 'type': 'function', 'function': {'name': 'xxx', 'arguments': '{...}'}}`
   - Automatically convert `args` object to JSON string (if needed)

4. **Content Type Handling**
   - Supports string, dict, list types
   - Non-string types automatically converted to JSON string

**Implementation Location**: `utils/message_converters.py`

### LangGraph Agent (gns3_copilot.py)

**File**: `gns3server/agent/gns3_copilot/agent/gns3_copilot.py`

**Responsibility**: LangGraph-based workflow orchestration for AI conversation

**Main Components**:

1. **llm_call Node**: Invokes LLM with tools and conversation history
   - Injects topology information into system prompt
   - Handles message trimming for context window management
   - Routes to tool execution or generates response

2. **tool_node Function**: Executes tool calls and returns results
   - **Critical**: Serializes tool output to JSON before creating ToolMessage
   - This ensures both SSE streaming and history storage use consistent JSON format
   - Implementation:
     ```python
     # Serialize observation to JSON string if it's not already a string
     if not isinstance(observation, str):
         observation = json.dumps(observation, ensure_ascii=False, indent=2)

     tool_msg = ToolMessage(
         content=observation,  # Always JSON string format
         tool_call_id=tool_call["id"],
         name=tool_call["name"],
         metadata={"created_at": datetime.utcnow().isoformat()}
     )
     ```

3. **generate_title Node**: Auto-generates conversation title on first interaction

**Why Serialize in tool_node?**

- **SSE Streaming**: `on_tool_end` event receives `ToolMessage.content` directly
- **History Storage**: ToolMessages are persisted to checkpoint database
- **Consistency**: Both paths use the same JSON format

Without serialization, LangChain would convert dict/list to Python str() representation
(single quotes, non-JSON format) when saving to history.

**Tool Output Data Flow**:

```
Tool.invoke() → dict/list
         ↓
tool_node() → json.dumps() → JSON string
         ↓
ToolMessage(content=JSON_string)
         ↓
┌────────────────┬─────────────────┐
│  SSE Stream    │   History DB    │
│  (agent_service)│  (checkpoints)  │
└────────────────┴─────────────────┘
         ↓
   Frontend receives standard JSON
```

### AgentService

**Responsibility**: Project-level Agent management service

**Main Methods**:
- `stream_chat`: Streaming conversation, automatically manages sessions and statistics
- `get_history`: Get session history
- `list_sessions`: List sessions
- `delete_session`: Delete session
- `rename_session`: Rename session
- `close`: Close database connection

**Core Flow** (stream_chat):
1. Initialize checkpointer connection (if not connected)
2. Get or create chat session (from `chat_sessions` table)
3. Set ContextVars (JWT token, LLM config)
4. Build LangGraph config
5. Create initial message with ID and timestamp: `HumanMessage(content=message, id=str(uuid4()), metadata={"created_at": datetime.utcnow().isoformat()})`
6. Stream Agent execution, collecting statistics simultaneously
7. Update session statistics to database after stream ends
8. Sync auto-generated title

**Statistics Collection Mechanism** (in `stream_chat`):

- Listen to LangGraph's `astream_events` event stream
- Collect statistics in real-time during event loop
- Statistics logic doesn't depend on converted SSE chunk, gets directly from original events

**Key Event Handling**:
- `on_chat_model_start`: LLM call count +1
- `on_chat_model_end`: Extract token usage (from `output.usage_metadata`), AI message count +1
- `on_tool_end`: Tool message count +1

**Implementation Location**: `agent_service.py`

### ProjectAgentManager

**Responsibility**: Global singleton, manages AgentService instances for all projects

**Methods**:
- `get_agent(project_id, project_path)`: Get or create project's AgentService
- `remove_agent(project_id)`: Remove project's AgentService
- `close_all`: Close all AgentService

### Chat API Routes

**File**: `gns3server/api/routes/controller/chat.py`

**Route Registration**:
```python
router.include_router(
    chat.router,
    prefix="/{project_id}/chat",
    tags=["Chat"]
)
```

**Main Endpoint Implementation**:
- All endpoints require user authentication (`get_current_active_user`)
- All endpoints check if project status is "opened"
- stream endpoint uses `StreamingResponse` to return SSE stream

## Project Lifecycle Integration

### When Project Opens

Create or get AgentService instance:
```python
agent_manager = await get_project_agent_manager()
agent_service = await agent_manager.get_agent(project_id, project.path)
```

### When Project Closes

Remove AgentService instance, release resources:
```python
agent_manager.remove_agent(project_id)
```

### When Project Deletes

1. Call `delete_all_sessions(project_id)` to delete all sessions and checkpoint data
2. Remove AgentService instance
3. Project directory is deleted, database file is also deleted

## Frontend Integration

### useChat Hook

Handle different types based on SSE message's `type` field:

| type | Handling Logic |
|------|----------------|
| content | Append to current AI message content |
| tool_call | Create tool_call type message, display tool call information |
| tool_start | Optional: show tool start execution status |
| tool_end | Create tool_result type message, display tool execution result |
| error | Display error message |
| done | Mark stream end, stop loading state |
| heartbeat | Ignore (keepalive signal) |

### Session ID Management (Important)

The frontend must properly manage session_id to maintain conversation continuity:

1. **First request**: Do not include `session_id` in request body
2. **Save session_id**: Extract `session_id` from each SSE message (especially the `done` message)
3. **Subsequent requests**: Include the saved `session_id` in request body to continue the conversation
4. **State management**: Store `session_id` in React state/localStorage to persist across page refreshes

**Example**:
```javascript
// First message
const response = await fetch('/chat/stream', {
  method: 'POST',
  body: JSON.stringify({ message: 'Hello', stream: true })
});

// Get session_id from first done message
let sessionId = null;
for await (const chunk of reader) {
  const data = JSON.parse(chunk.data);
  if (data.type === 'done') {
    sessionId = data.session_id;
    break;
  }
}

// Subsequent messages - include session_id
await fetch('/chat/stream', {
  method: 'POST',
  body: JSON.stringify({ message: 'Continue conversation', session_id: sessionId, stream: true })
});
```

### Message Timestamp

Each message includes a timestamp in the `metadata` field:

- **Field location**: `message.metadata.created_at`
- **Format**: ISO 8601 (e.g., `"2026-03-08T01:33:17.848519"`)
- **Note**: Historical messages may have empty `metadata` ({}) if created before this feature was added

**Example**:
```javascript
// Read message timestamp
const timestamp = message.metadata?.created_at;
const displayTime = timestamp ? new Date(timestamp).toLocaleString() : 'Unknown';
```

### Error Handling

- Network error: Show retry option
- LLM error: Show error message
- Project not opened: Prompt user to open project
- LLM not configured: Guide user to configure LLM

## Security Considerations

### User Isolation

- Each user can only access their own sessions
- user_id stored in config.metadata
- All database queries filtered by user_id

### Project Access Control

- Only allow access to projects user has permission for
- Project status check: only allow "opened" status projects to use Chat

### LLM Configuration Security

- API key encrypted storage in database
- Pass via ContextVars, not persisted to checkpoint
- Automatically clear sensitive information in memory after request ends

## Performance Optimization

### Database Connection Management

- Use WAL mode to improve concurrent write performance
- Project-level connection reuse
- Automatically close old connections when switching projects

### Checkpoint Optimization

- LangGraph automatically manages checkpoints table
- Periodically clean old checkpoints (optional)
- Use indexes to accelerate queries (thread_id, user_id + project_id)

### Statistics Collection and Update

**Collection Mechanism** (in-memory):
- Collect statistics synchronously during SSE streaming transmission
- Listen to LangGraph event stream, no additional network overhead
- Use temporary variables to accumulate statistics, avoid frequent database access

**Update Strategy** (batch write after stream ends):
- After streaming Chat completes, update `chat_sessions` table in one batch
- Use SQL incremental update syntax: `message_count = message_count + ?`
- Single database transaction, commit all statistic updates

**Advantages**:
- Reduce database write count (N events → 1 update)
- Lower database lock contention
- Improve real-time performance of streaming response

**Implementation Location**: `agent_service.py` lines 283-294

## Dependencies

- `langchain` >= 0.3.0
- `langgraph` >= 0.2.0
- `langchain-core`
- `langgraph-checkpoint-sqlite` >= 3.0.1
- `aiosqlite`

## Extensibility

### Reserved Fields

- `metadata` (TEXT JSON): Store session-level metadata
- `stats` (TEXT JSON): Store additional statistics

### Future Possible Extensions

#### Runtime LLM Parameter Override

Current LLM configuration (including temperature, max_tokens, etc.) is read from user's database configuration. Future support for overriding these parameters at request time:

**Implementation Plan**:
```python
# In chat.py's stream_chat function
if request.temperature is not None:
    llm_config["temperature"] = str(request.temperature)
if request.max_tokens is not None:
    llm_config["max_tokens"] = str(request.max_tokens)
```

**Current Status**:
- `temperature` parameter already added to ChatRequest schema, but override logic not implemented
- Parameter reserved in API for backward compatibility
- TODO comments added in code to mark implementation location

**Notes**:
- Need to validate parameter ranges (e.g., temperature: 0.0-2.0)
- Need to consider whether to record override values to statistics
- Need to provide corresponding settings in frontend UI

#### Other Extension Directions

- Multi-modal support (images, files)
- Voice input/output
- Multi-user collaboration sessions
- Session sharing and export
- Custom tool registration

## References

- [LangGraph Checkpoint Documentation](https://langchain-ai.github.io/langgraph/how-tos/checkpointers/)
- [Server-Sent Events (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [OpenAI Chat Format](https://platform.openai.com/docs/api-reference/chat)


