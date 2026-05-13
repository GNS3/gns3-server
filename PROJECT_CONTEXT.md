# GNS3 Server - Project Context for Claude Code

> This document provides project context information for the Claude Code AI assistant to work more efficiently.

---

## Project Overview

**Project Name**: GNS3 Server
**Description**: Network simulation server supporting the GNS3 network virtualization platform
**Primary Language**: Python
**Current Branch**: `feature/ai-copilot-bridge`
**Main Branch**: `master`

---

## Project Structure

```
gns3server/
├── agent/                          # AI Copilot related modules
│   └── gns3_copilot/              # GNS3-Copilot AI Assistant
│       ├── agent/                  # LangGraph Agent implementation
│       ├── tools_v2/               # Tool collection (device config, display commands, etc.)
│       ├── utils/                  # Utility functions and helper modules
│       ├── gns3_client/            # GNS3 API client
│       ├── prompts/                # AI prompt templates
│       ├── agent_service.py        # Agent service layer
│       └── project_agent_manager.py # Project Agent manager
│
├── api/                            # API routes
│   └── routes/controller/          # Controller API
│       └── chat.py                 # AI Chat API endpoint
│
├── controller/                     # Core controller
│   ├── project.py                  # Project management
│   └── ...
│
├── schemas/                        # Pydantic data models
│   └── controller/
│       └── chat.py                 # Chat API Schema
│
├── db/                             # Database module
│   └── tasks.py                    # Database tasks
│
└── docs/                           # Documentation
    └── gns3-copilot/               # AI Copilot documentation
```

---

## Key Module Descriptions

### 1. AI Copilot Data Flow

```
Tool Layer → Agent Layer → Service Layer → API Layer → Frontend
```

**Tool Output Format**: All tools return `dict` or `list[dict]`, automatically serialized to JSON in the Service layer

**Key Files**:
- `agent/gns3_copilot/tools_v2/*.py` - Tool implementations
- `agent/gns3_copilot/agent_service.py:460-473` - Event conversion logic
- `agent/gns3_copilot/utils/parse_tool_content.py` - Tool result parsing

### 2. SSE Event Types

| Type | Description |
|------|-------------|
| `content` | AI text streaming output |
| `tool_call` | LLM tool invocation (progressive parameters) |
| `tool_start` | Tool execution started |
| `tool_end` | Tool execution completed (output as JSON) |
| `error` | Error message |
| `done` | Stream ended |

### 3. Important Tools

| Tool Name | File | Function |
|-----------|------|----------|
| `ExecuteMultipleDeviceCommands` | `display_tools_nornir.py` | Read-only diagnostic commands |
| `ExecuteMultipleDeviceConfigCommands` | `config_tools_nornir.py` | Configuration commands |
| `VPCSMultiCommands` | `vpcs_tools_telnetlib3.py` | VPCS virtual PC commands |
| `GNS3TemplateTool` | `gns3_get_node_temp.py` | Get GNS3 templates |
| `GNS3CreateNodeTool` | `gns3_create_node.py` | Create nodes |

---

## Code Standards

### Static Code Analysis (Flake8)

The project uses **flake8** for static code analysis. You must run checks before committing code.

#### Running Flake8

```bash
# Activate virtual environment
source venv/bin/activate

# Check a single file
flake8 path/to/file.py

# Check the entire project
flake8 gns3server/

# Check a specific directory
flake8 gns3server/utils/
```

#### Common Flake8 Error Codes

| Code | Description | Example |
|------|-------------|---------|
| **F401** | Module imported but unused | `import os` never used |
| **F841** | Local variable assigned but never used | `x = 1` not used later |
| **F824** | `global` declaration never assigned | `global _bar` never assigned in scope |
| **E501** | Line too long (>79 characters) | Single line exceeds 79 characters |

#### Fix Examples

```python
# F401: Remove unused imports
# Bad
import os  # Never used
# Good: Delete this line

# F841: Mark as intentionally unused
# Bad
def foo():
    x = 1  # Never used

# Good: Use or mark as intentionally unused
def foo():
    x = 1
    _ = x  # Mark as intentionally unused

# F824: Remove unnecessary global declaration
# Bad
def foo():
    global _fernet  # Never assigned in this scope

# Good: Remove global statement (if only reading)
def foo():
    # Just read the global variable, no global declaration needed
    pass

# E501: Break long lines
# Bad
raise RuntimeError("Encryption not initialized. Call init_encryption() first.")

# Good
raise RuntimeError(
    "Encryption not initialized. Call init_encryption() first."
)
```

#### Ruff (Alternative)

[Ruff](https://docs.astral.sh/ruff/) is a faster Python linter that can replace flake8, isort, black, and more.

```bash
# Install
pip install ruff

# Usage
ruff check gns3server/          # Check code
ruff check --fix gns3server/    # Auto-fix
ruff format gns3server/         # Format code
```

### Python Code Style

```python
# 1. Type annotations
def process_data(input_data: dict[str, Any]) -> list[dict[str, Any]]:
    pass

# 2. Error handling
try:
    result = tool.invoke(args)
except Exception as e:
    logger.error("Tool failed: %s", e, exc_info=True)
    return {"error": str(e)}

# 3. JSON serialization
if not isinstance(output, str):
    output = json.dumps(output, ensure_ascii=False, indent=2)
```

### Import Order

```python
# 1. Standard library
import asyncio
import json
import logging

# 2. Third-party libraries
from langchain.tools import BaseTool
from pydantic import BaseModel

# 3. Local modules
from gns3server.agent.gns3_copilot.agent import agent_builder
from gns3server.controller import Controller
```

### Copyright Header

```python
# SPDX-License-Identifier: GPL-3.0-or-later
#
# GNS3-Copilot - AI-powered Network Lab Assistant for GNS3
#
# Copyright (C) 2025 Yue Guobin (岳国宾)
# Author: Yue Guobin (岳国宾)
#
# Project Home: https://github.com/yueguobin/gns3-copilot
```

---

## Git Commit Standards

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Type Categories

| Type | Description | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(copilot): add user authentication` |
| `fix` | Bug fix | `fix(api): correct JSON serialization` |
| `docs` | Documentation update | `docs: update API design doc` |
| `refactor` | Refactoring | `refactor(agent): simplify state management` |
| `chore` | Build/toolchain | `chore: update dependencies` |

### Example

```
fix(copilot): serialize tool output to standard JSON format

Changed tool output serialization in AgentService._convert_event_to_chunk()
from str() to json.dumps() to ensure structured data is properly formatted.

Changes:
- Added json import to agent_service.py
- Modified on_tool_end event handling

Benefits:
- Frontend can parse tool results with JSON.parse()
- Chinese characters are preserved (not escaped)

Co-Authored-By: YueGuobin <yueguobin@outlook.com>
```

### IMPORTANT: Use Your Own Git Account for Commits

When creating git commits, **ALWAYS** use your own git account information for authorship.

**Before committing**, verify your git configuration:

```bash
# Check current git user configuration
git config user.name
git config user.email

# If incorrect, set your own information
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

**For this project**, the current configured user is:
```
Name:  YueGuobin
Email: yueguobin@outlook.com
```

You may use `Co-Authored-By` to credit contributors, but the `Author` field should always be **your own account**:

```bash
git commit -m "feat: add new feature

Co-Authored-By: ContributorName <contributor@example.com>"
```

---

## Development Notes

### 1. When Modifying Tool Output Format

**Must update the following locations**:
- `agent/gns3_copilot/tools_v2/*.py` - Tool implementation
- `agent/gns3_copilot/agent_service.py` - Event conversion
- `docs/gns3-copilot/ai-chat-api-design.md` - API documentation

### 2. Data Serialization Principles

- **Tool Layer**: Return Python `dict`/`list`
- **Service Layer**: Use `json.dumps()` for serialization
- **API Layer**: Use Pydantic validation then serialize to SSE

### 3. Logging

```python
logger.info("Operation started: project_id=%s", project_id)
logger.debug("Detailed info: data=%s", data)
logger.error("Error occurred: %s", error, exc_info=True)
```

### 4. Security Considerations

- Prohibit dangerous commands (reload, erase startup-config, etc.)
- Use `filter_forbidden_commands()` to filter commands
- Validate user input (project_id format, etc.)

---

## Common Commands

```bash
# Run tests
pytest tests/

# Static code analysis (must run before committing)
source venv/bin/activate
flake8 gns3server/

# Check a single file
flake8 path/to/file.py

# Syntax check
python3 -m py_compile gns3server/agent/gns3_copilot/agent_service.py

# Check git status
git status

# View git history
git log --oneline -15

# View file modification history
git blame file.py -L 100,120

# Commit code (verify your git user info first!)
git config user.name && git config user.email
git add files...
git commit -m "type(scope): description"
```

---

## Related Documentation

- [AI Chat API Design](./docs/gns3-copilot/ai-chat-api-design.md)
- [Command Security Policy](./docs/gns3-copilot/command-security.md)
- [LLM Model Configuration](./docs/gns3-copilot/llm-model-configs-api.md)
- [Context Window Management](./docs/gns3-copilot/context-window-management.md)

---

**Document Maintenance**: Please update this document promptly when project structure or development standards change.
