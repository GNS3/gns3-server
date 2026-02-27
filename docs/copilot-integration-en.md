# GNS3 Server Copilot AI Agent Integration

## Overview

This document describes the AI Copilot Agent feature integrated into GNS3 Server, built using LangChain and LangGraph to provide intelligent network topology management and automation capabilities.

## Architecture Design

### Technology Stack

```
┌─────────────────────────────────────────────────────────┐
│  Presentation Layer: FastAPI                            │
│  /v3/copilot/* - Configuration Management API           │
│  /v3/projects/{id}/copilot/* - Project Chat API         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Service Layer: CopilotService                          │
│  - Agent lifecycle management                            │
│  - Tool binding                                          │
│  - Conversation state management                         │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  AI Framework: LangChain + LangGraph                     │
│  - LangChain: Models, tools, messages                    │
│  - LangGraph: State machine, workflow orchestration      │
│  - Checkpoint: Conversation persistence                  │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Tool Layer: Copilot Tools                               │
│  - Topology management, node operations, link creation   │
│  - Command execution (display/config/VPCS)               │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  Data Layer                                              │
│  - User configuration: copilot_configs table             │
│  - Project conversations: {project_dir}/copilot_checkpoints.db │
└─────────────────────────────────────────────────────────┘
```

## Directory Structure

```
gns3server/
├── db/
│   ├── models/
│   │   └── copilot.py                 # CopilotConfig data model
│   └── repositories/
│       └── copilot.py                 # CopilotRepository data repository
│
├── schemas/
│   └── controller/
│       └── copilot.py                 # API Schemas (request/response models)
│
├── api/routes/controller/
│   ├── copilot.py                     # Configuration management API
│   └── copilot_chat.py                # Chat API
│
├── services/
│   ├── copilot_service.py             # CopilotAgent service
│   ├── copilot_prompts/               # System prompts
│   │   ├── __init__.py
│   │   └── base_prompt.py             # From gns3-copilot
│   └── copilot_tools/                 # Tools collection
│       ├── __init__.py
│       ├── base.py                    # Tool base class
│       ├── topology.py                # Topology tools
│       ├── nodes.py                   # Node tools
│       ├── links.py                   # Link tools
│       ├── templates.py               # Template tools
│       ├── network_commands.py        # Network command tools
│       └── vpcs.py                    # VPCS tools
```

## Feature Modules

### 1. Configuration Management API

#### Create Configuration
```bash
POST /v3/copilot/config
Content-Type: application/json
Authorization: Bearer <token>

{
  "provider": "openai",
  "model_name": "gpt-4o",
  "api_key": "sk-xxx",
  "temperature": 0.7,
  "enabled": true
}
```

#### Get Configuration
```bash
GET /v3/copilot/config
Authorization: Bearer <token>
```

#### Update Configuration
```bash
PUT /v3/copilot/config
Content-Type: application/json

{
  "temperature": 0.5,
  "model_name": "gpt-4o-mini"
}
```

#### Delete Configuration
```bash
DELETE /v3/copilot/config
```

### 2. Chat API

#### Non-streaming Chat
```bash
POST /v3/projects/{project_id}/copilot/chat
Content-Type: application/json

{
  "message": "Help me create two routers and connect them",
  "conversation_id": "session-123"
}

Response:
{
  "response": "Sure, I'll help you create two routers...",
  "conversation_id": "session-123",
  "tools_used": ["list_gns3_templates", "create_gns3_node", ...]
}
```

#### Streaming Chat (SSE)
```bash
POST /v3/projects/{project_id}/copilot/chat/stream
Content-Type: application/json

{
  "message": "Create topology",
  "stream": true
}

# Returns Server-Sent Events
event: token
data: {"data": "Sure", "conversation_id": "session-123"}

event: tool_call
data: {"data": "list_gns3_templates", "conversation_id": "session-123"}

event: done
data: {"data": "", "conversation_id": "session-123"}
```

## Tool List

| Tool Name | Function | Description |
|---------|------|------|
| `list_gns3_templates` | List templates | Get available node templates |
| `get_gns3_topology` | Read topology | Get project topology information |
| `create_gns3_node` | Create node | Create new node in project |
| `start_gns3_node` | Start node | Start specified node |
| `create_gns3_link` | Create link | Connect two nodes |
| `execute_display_commands` | Display commands | Execute show commands (read-only) |
| `execute_config_commands` | Config commands | Execute configuration commands (modify devices) |
| `execute_vpcs_commands` | VPCS commands | Execute VPCS device commands |

## Checkpoint Conversation Persistence

### Storage Location

```
Project-level storage: {project_dir}/copilot_checkpoints.db

Example:
/var/lib/gns3/projects/abc-123-def/copilot_checkpoints.db
```

### Advantages

1. **Project-level isolation**: Each project has independent conversation history
2. **Team collaboration**: Multiple users share project conversation context
3. **Data management**: Conversation history automatically cleaned when project is deleted
4. **Project export**: Conversation history included when exporting project

### Usage

```python
# Multiple conversation rounds in the same project
await chat("Create router R1", project_id="abc", conversation_id="session-1")
await chat("Create switch S1", project_id="abc", conversation_id="session-1")

# Agent remembers R1 was created and can connect correctly
```

## Database Model

### CopilotConfig Table

```sql
CREATE TABLE copilot_configs (
    config_id VARCHAR(32) PRIMARY KEY,
    user_id VARCHAR(32) UNIQUE NOT NULL,
    provider VARCHAR(50) DEFAULT 'openai',
    model_name VARCHAR(100) DEFAULT 'gpt-4o',
    api_key VARCHAR(500),
    base_url VARCHAR(500),
    temperature FLOAT DEFAULT 0.7,
    max_tokens INTEGER,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
```

## Dependencies

### Python Packages

```txt
# LangChain and LangGraph
langchain>=1.2.0
langchain-core>=1.2.6
langgraph>=1.0.5
langgraph-checkpoint-sqlite>=3.0.1

# LLM Providers
langchain-openai>=1.1.6
langchain-anthropic>=1.3.1
langchain-google-genai>=4.1.3
langchain-aws>=1.2.0
langchain-ollama>=1.0.1

# Network Automation
netmiko>=4.6.0
nornir>=3.5.0
nornir-netmiko>=1.0.1
nornir-utils>=0.2.0
nornir-salt>=0.23.0
telnetlib3>=2.0.8
```

## Workflow

### Agent Execution Flow

```
1. User sends message
   ↓
2. Get project-specific Agent (with project Checkpoint)
   ↓
3. Build system message (including project topology)
   ↓
4. LLM analyzes and decides whether to call tools
   ↓
5. If tools needed:
   - Execute tool calls
   - Get results
   - Return to LLM for further processing
   ↓
6. Generate final response
   ↓
7. Save conversation state to project Checkpoint
```

### Tool Call Example

```
User: "Create two routers and connect them"
   ↓
LLM: Decides to call list_gns3_templates
   ↓
Tool: Returns available template list
   ↓
LLM: Decides to call create_gns3_node (create R1)
   ↓
Tool: Returns creation success
   ↓
LLM: Decides to call create_gns3_node (create R2)
   ↓
Tool: Returns creation success
   ↓
LLM: Decides to call create_gns3_link
   ↓
Tool: Returns connection success
   ↓
LLM: Generates final response
```

## Configuration

### Supported Providers

| Provider | Description | Example Models |
|----------|------|----------|
| `openai` | OpenAI | gpt-4o, gpt-4o-mini |
| `anthropic` | Anthropic | claude-3-5-sonnet-20241022 |
| `google` | Google AI | gemini-2.0-flash-exp |
| `aws` | AWS Bedrock | anthropic.claude-3-5-sonnet-20241022-v2:0 |
| `ollama` | Ollama local | llama3.2, qwen2.5 |
| `deepseek` | DeepSeek | deepseek-chat |
| `xai` | xAI | grok-2-1212 |

### Configuration Parameters

| Parameter | Type | Default | Description |
|------|------|--------|------|
| `provider` | string | "openai" | Model provider |
| `model_name` | string | "gpt-4o" | Model name |
| `api_key` | string | required | API key |
| `base_url` | string | null | Custom API endpoint |
| `temperature` | float | 0.7 | Temperature (0.0-2.0) |
| `max_tokens` | integer | null | Maximum token count |
| `enabled` | boolean | true | Whether enabled |

## Usage Examples

### Complete Workflow

```bash
# 1. Login to get token
TOKEN=$(curl -X POST http://localhost:3080/v3/access/users/login \
  -d "username=admin&password=admin" | jq -r '.access_token')

# 2. Create Copilot configuration
curl -X POST http://localhost:3080/v3/copilot/config \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "model_name": "gpt-4o",
    "api_key": "sk-xxxx",
    "temperature": 0.7
  }'

# 3. Use AI Agent to create topology
PROJECT_ID="your-project-id"
curl -X POST http://localhost:3080/v3/projects/$PROJECT_ID/copilot/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Help me create a network topology with three routers connected in a ring"
  }'

# Agent will automatically:
# 1. Call list_gns3_templates to view available templates
# 2. Call create_gns3_node to create three routers
# 3. Call create_gns3_link to connect them in a ring
# 4. Return complete execution results
```

## FAQ

### Q: Where is conversation history saved?
A: Saved in the `copilot_checkpoints.db` file in the project directory.

### Q: Is conversation history shared when multiple users collaborate on the same project?
A: Yes, because checkpoint is project-based, all users share that project's conversation history.

### Q: How do I delete conversation history?
A: Conversation history is automatically cleaned when the project is deleted, or manually delete the `copilot_checkpoints.db` file.

### Q: Which LLM providers are supported?
A: OpenAI, Anthropic, Google, AWS, Ollama, DeepSeek, xAI, etc.

### Q: What operations can the Agent perform?
A: Create nodes, create links, start nodes, execute network commands, read topology, etc.

## API Endpoint Overview

```
# Configuration Management
POST   /v3/copilot/config     # Create configuration
GET    /v3/copilot/config     # Get configuration
PUT    /v3/copilot/config     # Update configuration
DELETE /v3/copilot/config     # Delete configuration

# Project Chat
POST   /v3/projects/{id}/copilot/chat         # Non-streaming chat
POST   /v3/projects/{id}/copilot/chat/stream  # Streaming chat (SSE)
```

## Performance Considerations

1. **Agent caching**: Agents cached by project to avoid repeated creation
2. **Tool concurrency**: Nornir automatically executes multi-device commands concurrently
3. **Checkpoint efficiency**: SQLite lightweight persistence
4. **Streaming response**: Supports real-time streaming return for better user experience

## Security Notes

1. **API Key encryption**: Currently stored in plaintext, production environment recommends encryption
2. **User isolation**: Each user has independent configuration
3. **Permission control**: Valid user token required
4. **Project access**: Users can only access projects they have permissions for

## Future Development Plans

- [ ] API Key encrypted storage
- [ ] Support for more network device types
- [ ] Conversation history management API
- [ ] Tool execution result caching
- [ ] More detailed error handling and logging
- [ ] Unit tests and integration tests

## Related Documentation

- [LangChain Documentation](https://python.langchain.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [gns3-copilot Project](https://github.com/yueguobin/gns3-copilot)
