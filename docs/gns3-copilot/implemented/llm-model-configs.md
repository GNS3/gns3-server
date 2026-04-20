<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This documentation is organized by AI with reference to actual code. AI can make mistakes — please verify against the source code when in doubt.


# LLM Model Configurations API

## Overview

This API provides LLM model configuration management for users and user groups with inheritance support.

### Key Features

- **User-level configurations**: Each user can have their own LLM model configurations
- **Group-level configurations**: User groups can share LLM model configurations
- **Inheritance**: Users automatically inherit configurations from their groups (when they have no own configs)
- **Default configuration**: Both users and groups can set a default configuration
- **API Key Encryption**: API keys are automatically encrypted in the database
- **Optimistic Locking**: Prevents concurrent modification conflicts using version tracking

### Inheritance Logic

```
User requests configs:
  ├─ Always return user's own configs (if any)
  └─ Always return inherited group configs (if any)
```

**Note:** Users can see both their own configurations AND configurations inherited from their groups. The `source` field in the response indicates the origin of each configuration.

### Configuration Priority

```
User's own config > User's group config
```

---

## Database Schema

### Table: `llm_model_configs`

| Column | Type | Description |
|--------|------|-------------|
| `config_id` | UUID | Primary key |
| `name` | VARCHAR(100) | Configuration name (table-level for indexing) |
| `model_type` | VARCHAR(50) | Model type (table-level for filtering) |
| `config` | JSON (JSONB on PostgreSQL) | Configuration data (provider, base_url, model, temperature, api_key, etc.) |
| `user_id` | UUID (nullable) | Foreign key to users table |
| `group_id` | UUID (nullable) | Foreign key to user_groups table |
| `is_default` | BOOLEAN | Default configuration flag |
| `version` | INTEGER | Optimistic locking version (starts at 0, increments on each update) |
| `created_at` | TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMP | Last update timestamp |

### Model Types

The `model_type` field accepts the following values:
- `text` - Text generation models
- `vision` - Vision/image understanding models
- `stt` - Speech-to-Text models
- `tts` - Text-to-Speech models
- `multimodal` - Multimodal models supporting multiple input types
- `embedding` - Text embedding models
- `reranking` - Reranking models
- `other` - Other model types

### Constraints

- Each config belongs to **either** a user **or** a group (not both)
- Each user can have **at most one** default configuration
- Each group can have **at most one** default configuration
- `version` field is automatically incremented on each update

---

## Supported Providers

GNS3-Copilot uses LangChain's `init_chat_model` function, which supports the following LLM providers:

### Provider List

| Provider | Provider Value | Default base_url | base_url Required? | Notes |
|----------|---------------|------------------|-------------------|-------|
| OpenAI | `openai` | `https://api.openai.com/v1` | ✅ Yes (planned optional) | Most popular, supports GPT-4, GPT-3.5 |
| Anthropic | `anthropic` | `https://api.anthropic.com` | ✅ Yes (planned optional) | Claude 3.5 Sonnet, Claude 3 Opus |
| Google | `google` | `https://generativelanguage.googleapis.com` | ✅ Yes (planned optional) | Gemini Pro, Gemini Flash |
| AWS Bedrock | `aws` | Varies by region | ✅ Yes | Requires AWS configuration |
| Ollama | `ollama` | `http://localhost:11434` | ✅ Yes | Local models, typically running on localhost |
| DeepSeek | `deepseek` | `https://api.deepseek.com` | ✅ Yes (planned optional) | DeepSeek Chat, DeepSeek Coder |
| xAI | `xai` | `https://api.x.ai` | ✅ Yes (planned optional) | Grok models |

> **Note:** The `base_url` field is currently **required** in the API schema for all providers. Entries marked "planned optional" indicate providers where `base_url` may become optional in a future release (see [Future Enhancements](#optional-base_url-field)). For now, use the default endpoint URL listed in the table.

### When to Specify `base_url`

You only need to specify the `base_url` parameter in these scenarios:

1. **Using Ollama**: Always required (e.g., `http://localhost:11434`)
2. **Using AWS Bedrock**: Required, depends on your AWS region configuration
3. **Using a proxy or custom endpoint**: If you're accessing the provider through a proxy
4. **Using OpenAI-compatible services**: Such as Azure OpenAI, local deployments, or third-party APIs
5. **Self-hosted or custom deployments**: When running your own model server

### Example Configurations by Provider

#### OpenAI (No base_url needed)
```json
{
  "name": "GPT-4o",
  "model_type": "text",
  "provider": "openai",
  "model": "gpt-4o",
  "temperature": 0.7,
  "context_limit": 128,
  "api_key": "sk-..."
}
```

#### Anthropic (No base_url needed)
```json
{
  "name": "Claude-3.5 Sonnet",
  "model_type": "text",
  "provider": "anthropic",
  "model": "claude-3-5-sonnet-20241022",
  "temperature": 0.7,
  "context_limit": 200,
  "api_key": "sk-ant-..."
}
```

#### Ollama (base_url required)
```json
{
  "name": "Llama-3-Local",
  "model_type": "text",
  "provider": "ollama",
  "base_url": "http://localhost:11434",
  "model": "llama3",
  "temperature": 0.7,
  "context_limit": 8
}
```

#### Azure OpenAI (custom base_url)
```json
{
  "name": "Azure-GPT-4",
  "model_type": "text",
  "provider": "openai",
  "base_url": "https://your-resource.openai.azure.com/openai/deployments/your-deployment",
  "model": "gpt-4",
  "temperature": 0.7,
  "context_limit": 128,
  "api_key": "..."
}
```

### Adding New Providers

To add support for additional LangChain providers:

1. Install the corresponding LangChain provider package (e.g., `langchain-<provider>`)
2. Add the package to `ai-requirements.txt`
3. Use the provider's identifier value in the `provider` field

For a complete list of LangChain-supported providers, see: https://python.langchain.com/docs/integrations/providers/

---

## API Endpoints

### User Configuration Endpoints

| Method | Path | Description | Privilege |
|--------|------|-------------|-----------|
| GET | `/v3/access/users/{user_id}/llm-model-configs` | Get user's effective configs (own + inherited) | User.Audit |
| GET | `/v3/access/users/{user_id}/llm-model-configs/own` | Get user's own configs only (returns `List[LLMModelConfigResponse]`, a plain array) | User.Audit |
| GET | `/v3/access/users/{user_id}/llm-model-configs/default` | Get user's default configuration | User.Audit |
| POST | `/v3/access/users/{user_id}/llm-model-configs` | Create a new configuration | User.Modify |
| PUT | `/v3/access/users/{user_id}/llm-model-configs/{config_id}` | Update a configuration | User.Modify |
| DELETE | `/v3/access/users/{user_id}/llm-model-configs/{config_id}` | Delete a configuration | User.Modify |
| PUT | `/v3/access/users/{user_id}/llm-model-configs/default/{config_id}` | Set default configuration | User.Modify |

### Group Configuration Endpoints

| Method | Path | Description | Privilege |
|--------|------|-------------|-----------|
| GET | `/v3/access/groups/{group_id}/llm-model-configs` | Get all group configurations | Group.Audit |
| GET | `/v3/access/groups/{group_id}/llm-model-configs/default` | Get group's default configuration | Group.Audit |
| POST | `/v3/access/groups/{group_id}/llm-model-configs` | Create a new configuration | Group.Modify |
| PUT | `/v3/access/groups/{group_id}/llm-model-configs/{config_id}` | Update a configuration | Group.Modify |
| DELETE | `/v3/access/groups/{group_id}/llm-model-configs/{config_id}` | Delete a configuration | Group.Modify |
| PUT | `/v3/access/groups/{group_id}/llm-model-configs/default/{config_id}` | Set default configuration | Group.Modify |

**Note:** The GET endpoints for groups return the same structure as user endpoints: `configs`, `default_config`, and `total`.

---

## Request/Response Schemas

### LLMModelConfigCreate

**Required Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Configuration name (1-100 chars) |
| `model_type` | string | Model type (text, vision, stt, tts, multimodal, embedding, reranking, other) |
| `provider` | string | LLM provider (e.g., "openai", "anthropic", "ollama"). See [Supported Providers](#supported-providers) below |
| `base_url` | string | API base URL (required). For mainstream providers, use their official endpoint. See [Supported Providers](#supported-providers) for default URLs |
| `model` | string | Model name |
| `temperature` | float | Temperature (0.0-2.0, default: 0.7) |
| `context_limit` | integer | **Model context window limit in K tokens** (e.g., 128 = 128K = 128,000 tokens) |

**Optional Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `api_key` | string | API key (auto-encrypted) |
| `max_tokens` | integer | **⚠️ Reserved for future use, not currently implemented** |
| `context_strategy` | string | Context trimming strategy: "conservative" (60%), "balanced" (75%), "aggressive" (85%). Default: "balanced" |
| `copilot_mode` | string | GNS3-Copilot mode: "teaching_assistant" (diagnostics only, default) or "lab_automation_assistant" (full configuration access) |
| `is_default` | boolean | Set as default (default: false) |

**Important Notes:**

- **`context_limit` is required**: You must specify the model's context window limit. Refer to the model provider's official documentation for the current value.
- **Unit is K tokens**: The value is in thousands of tokens (1 K = 1,000 tokens). For example:
  - GPT-4o: 128,000 tokens → configure as `"context_limit": 128`
  - Claude 3.5 Sonnet: 200,000 tokens → configure as `"context_limit": 200`
  - Gemini 1.5 Pro: 2,800,000 tokens → configure as `"context_limit": 2800`

**Extra Fields:** Any custom fields are supported for future extensibility.

### LLMModelConfigUpdate

| Field | Type | Description |
|-------|------|-------------|
| `name` | string (optional) | Configuration name |
| `model_type` | string (optional) | Model type |
| `provider` | string (optional) | LLM provider |
| `base_url` | string (optional) | API base URL |
| `model` | string (optional) | Model name |
| `temperature` | float (optional) | Temperature |
| `api_key` | string (optional) | API key |
| `max_tokens` | integer or string (optional) | **⚠️ Reserved for future use, not currently implemented**. Accepts integers, null, or the string "null" (which will be converted to null) |
| `context_limit` | integer (optional) | Model context window limit in K tokens |
| `context_strategy` | string (optional) | Context trimming strategy |
| `is_default` | boolean (optional) | Default flag |
| `copilot_mode` | string (optional) | GNS3-Copilot mode: "teaching_assistant" or "lab_automation_assistant" |
| `expected_version` | integer (optional) | **Optimistic locking version** |

**Note:** When using `expected_version`, the API will verify the version hasn't changed since you read the data. If it has, you'll receive a 409 Conflict error.

**Reserved Fields:**
- `max_tokens`: Reserved for future implementation. Currently not used by the system. The maximum output tokens are controlled automatically by the LLM provider based on the model and input size.

**Update Limitations:**
- `context_strategy` and `copilot_mode` can be set to new values but **cannot be cleared to null** via update. This is because the API filters out null values before processing.

### LLMModelConfigResponse

| Field | Type | Description |
|-------|------|-------------|
| `config_id` | UUID | Configuration ID |
| `name` | string | Configuration name |
| `model_type` | string | Model type |
| `config` | LLMModelConfigData | Configuration data (provider, base_url, model, temperature, etc.) |
| `user_id` | UUID (nullable) | Owner user ID |
| `group_id` | UUID (nullable) | Owner group ID |
| `is_default` | boolean | Default flag |
| `version` | integer | **Current version number** (for optimistic locking) |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Last update time |

### LLMModelConfigInheritedResponse

| Field | Type | Description |
|-------|------|-------------|
| `configs` | list[LLMModelConfigWithSource] | Effective configurations |
| `default_config` | LLMModelConfigWithSource (nullable) | Default configuration (never null if configs list is not empty) |
| `total` | integer | Total count |

**Default Configuration Selection Logic:**
1. User's config marked with `is_default: true` (highest priority)
2. Group's config marked with `is_default: true`
3. First config in the list (user configs come before group configs)

### LLMModelConfigListResponse

| Field | Type | Description |
|-------|------|-------------|
| `configs` | list[LLMModelConfigResponse] | Configuration list |
| `default_config` | LLMModelConfigResponse (nullable) | Default configuration (never null if configs list is not empty) |
| `total` | integer | Total count |

**Default Configuration Selection Logic:**
1. Config marked with `is_default: true`
2. First config in the list (fallback if no default is marked)

**Usage:** This schema is used for group configuration endpoints (e.g., `GET /groups/{group_id}/llm-model-configs`).

### LLMModelConfigWithSource

| Field | Type | Description |
|-------|------|-------------|
| `config_id` | UUID | Configuration ID |
| `name` | string | Configuration name |
| `model_type` | string | Model type |
| `config` | LLMModelConfigData | Configuration data (provider, base_url, model, temperature, etc.) |
| `user_id` | UUID (nullable) | Owner user ID |
| `group_id` | UUID (nullable) | Owner group ID |
| `is_default` | boolean | Default flag |
| `version` | integer | Optimistic locking version |
| `created_at` | TIMESTAMP | Creation time |
| `updated_at` | TIMESTAMP | Last update time |
| `source` | string | Source: "user" or "group" |
| `group_name` | string (nullable) | Group name if source is "group" |

---

## Usage Examples

### 1. Create a user configuration

```bash
curl -X POST http://localhost:3080/v3/access/users/{user_id}/llm-model-configs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GPT-4o",
    "model_type": "text",
    "provider": "openai",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o",
    "temperature": 0.7,
    "context_limit": 128,
    "context_strategy": "balanced",
    "api_key": "sk-xxx",
    "copilot_mode": "teaching_assistant",
    "is_default": true
  }'
```

**Important:**
- `context_limit` is **required** and specified in K tokens (e.g., 128 = 128K = 128,000 tokens)
- Refer to the model provider's official documentation for the current context window size
- **`base_url` is required** - you must provide a value. For mainstream providers (OpenAI, Anthropic, Google, DeepSeek, xAI), use their official endpoints listed in [Supported Providers](#supported-providers)

**Response:**
```json
{
  "config_id": "uuid-1",
  "name": "GPT-4o",
  "model_type": "text",
  "config": {
    "provider": "openai",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o",
    "temperature": 0.7,
    "context_limit": 128,
    "context_strategy": "balanced",
    "api_key": null,
    "copilot_mode": null
  },
  "user_id": "uuid-user",
  "group_id": null,
  "is_default": true,
  "version": 0,
  "created_at": "2026-03-03T12:00:00Z",
  "updated_at": "2026-03-03T12:00:00Z"
}
```

**Note:** The `api_key` field is always `null` in responses for security. The API key is encrypted and stored in the database, but never returned via the API.

### 2. Create a group configuration

```bash
curl -X POST http://localhost:3080/v3/access/groups/{group_id}/llm-model-configs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Claude-3.5 Sonnet",
    "model_type": "text",
    "provider": "anthropic",
    "base_url": "https://api.anthropic.com",
    "model": "claude-3-5-sonnet-20241022",
    "temperature": 0.7,
    "context_limit": 200,
    "context_strategy": "balanced",
    "api_key": "sk-ant-xxx",
    "copilot_mode": "lab_automation_assistant",
    "is_default": true
  }'
```

### 3. Get user's effective configurations (with inheritance)

```bash
curl -X GET http://localhost:3080/v3/access/users/{user_id}/llm-model-configs \
  -H "Authorization: Bearer <token>"
```

**Response (user has both own configs and inherited group configs):**
```json
{
  "configs": [
    {
      "config_id": "uuid-1",
      "name": "GPT-4o",
      "model_type": "text",
      "config": {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "temperature": 0.7,
        "context_limit": 128,
        "context_strategy": "balanced",
        "api_key": null,
        "copilot_mode": "lab_automation_assistant"
      },
      "user_id": "uuid-user",
      "group_id": null,
      "is_default": true,
      "version": 0,
      "created_at": "2026-03-03T14:32:48.158880Z",
      "updated_at": "2026-03-03T14:32:48.158880Z",
      "source": "user",
      "group_name": null
    },
    {
      "config_id": "uuid-2",
      "name": "Claude-3.5 Sonnet",
      "model_type": "text",
      "config": {
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com",
        "model": "claude-3-5-sonnet-20241022",
        "temperature": 0.7,
        "context_limit": 200,
        "context_strategy": "balanced",
        "api_key": null,
        "copilot_mode": null
      },
      "user_id": null,
      "group_id": "uuid-group",
      "is_default": true,
      "version": 0,
      "created_at": "2026-03-03T14:32:48.158880Z",
      "updated_at": "2026-03-03T14:32:48.158880Z",
      "source": "group",
      "group_name": "Developers"
    }
  ],
  "default_config": {
    "config_id": "uuid-1",
    "name": "GPT-4o",
    "model_type": "text",
    "config": {
      "provider": "openai",
      "base_url": "https://api.openai.com/v1",
      "model": "gpt-4o",
      "temperature": 0.7,
      "context_limit": 128,
      "context_strategy": "balanced",
      "api_key": null,
      "copilot_mode": "lab_automation_assistant"
    },
    "user_id": "uuid-user",
    "group_id": null,
    "is_default": true,
    "version": 0,
    ...
  },
  "total": 2
}
```

**Note:**
- All configs show `config.api_key: null` (always hidden for security)
- `source: "user"` indicates the config belongs to the user
- `source: "group"` indicates the config is inherited from a group
- Configuration fields are nested in the `config` object (same structure as group endpoints)
- `context_limit` is in K tokens (128 = 128K = 128,000 tokens)

### 4. Get group configurations

```bash
curl -X GET http://localhost:3080/v3/access/groups/{group_id}/llm-model-configs \
  -H "Authorization: Bearer <token>"
```

**Response:**
```json
{
  "configs": [
    {
      "config_id": "uuid-1",
      "name": "Claude-3",
      "model_type": "text",
      "config": {
        "provider": "anthropic",
        "base_url": "https://api.anthropic.com",
        "model": "claude-3-opus-20240229",
        "temperature": 0.7,
        "context_limit": 200,
        "context_strategy": "balanced",
        "api_key": null,
        "copilot_mode": null
      },
      "user_id": null,
      "group_id": "uuid-group",
      "is_default": true,
      "version": 0,
      "created_at": "2026-03-03T12:00:00Z",
      "updated_at": "2026-03-03T12:00:00Z"
    },
    {
      "config_id": "uuid-2",
      "name": "GPT-4",
      "model_type": "text",
      "config": {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4",
        "temperature": 0.7,
        "context_limit": 128,
        "context_strategy": "balanced",
        "api_key": null,
        "copilot_mode": null
      },
      "user_id": null,
      "group_id": "uuid-group",
      "is_default": false,
      "version": 0,
      "created_at": "2026-03-03T12:00:00Z",
      "updated_at": "2026-03-03T12:00:00Z"
    }
  ],
  "default_config": {
    "config_id": "uuid-1",
    "name": "Claude-3",
    "model_type": "text",
    "config": {
      "provider": "anthropic",
      ...
    },
    "user_id": null,
    "group_id": "uuid-group",
    "is_default": true,
    "version": 0,
    ...
  },
  "total": 2
}
```

**Note:** The response structure is the same as user endpoints, with `configs`, `default_config`, and `total` fields. All `api_key` values are `null` for security.

### 5. Update a configuration (without optimistic locking)

```bash
curl -X PUT http://localhost:3080/v3/access/users/{user_id}/llm-model-configs/{config_id} \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "temperature": 0.9,
    "max_tokens": 4000,
    "context_strategy": "aggressive"
  }'
```

### 6. Update a configuration (WITH optimistic locking)

**Best practice for avoiding concurrent modification conflicts:**

```bash
# Step 1: Read the config (get the current version)
curl -X GET http://localhost:3080/v3/access/users/{user_id}/llm-model-configs/own \
  -H "Authorization: Bearer <token>"

# Response includes "version": 5

# Step 2: Update with expected_version
curl -X PUT http://localhost:3080/v3/access/users/{user_id}/llm-model-configs/{config_id} \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "temperature": 0.9,
    "max_tokens": 4000,
    "expected_version": 5
  }'

# Response includes incremented "version": 6
```

**If someone else modified the config before you:**

```json
HTTP 409 Conflict
{
  "detail": "Concurrent modification detected. Expected version 5, but current version is 6. Please retry."
}
```

**Client retry flow:**
1. Receive 409 Conflict error
2. Re-fetch the config to get the latest version
3. Apply your changes on top of the latest data
4. Retry the update with the new `expected_version`

### 7. Set default configuration

```bash
curl -X PUT http://localhost:3080/v3/access/users/{user_id}/llm-model-configs/default/{config_id} \
  -H "Authorization: Bearer <token>"
```

### 8. Get default configuration

Get the user's default configuration:

```bash
curl -X GET http://localhost:3080/v3/access/users/{user_id}/llm-model-configs/default \
  -H "Authorization: Bearer <token>"
```

**Note:** This endpoint only returns configurations explicitly marked with `is_default: true`. If no configuration is marked as default, it returns 404.

**Response:**
```json
{
  "config_id": "uuid-1",
  "name": "GPT-4o",
  "model_type": "text",
  "config": {
    "provider": "openai",
    "base_url": "https://api.openai.com/v1",
    "model": "gpt-4o",
    "temperature": 0.7,
    "context_limit": 128,
    "context_strategy": "balanced",
    "api_key": null,
    "copilot_mode": null
  },
  "user_id": "uuid-user",
  "group_id": null,
  "is_default": true,
  "version": 0,
  "created_at": "2026-03-03T18:15:00Z",
  "updated_at": "2026-03-03T18:15:00Z"
}
```

**Note:** The `api_key` field is always `null` in responses for security.

**If no default configuration is set:**

```json
HTTP 404 Not Found
{
  "detail": "No default LLM model configuration found for user '{user_id}'"
}
```

Get the group's default configuration:

```bash
curl -X GET http://localhost:3080/v3/access/groups/{group_id}/llm-model-configs/default \
  -H "Authorization: Bearer <token>"
```

The response format is the same as for users.

---

**Important Note:** This dedicated `/default` endpoint is different from the `default_config` field in the list response:
- `/default` endpoint: Requires explicit `is_default: true` flag, returns 404 if not found
- `default_config` field in list: Falls back to first config if no explicit default is marked

### 9. Delete a configuration

```bash
curl -X DELETE http://localhost:3080/v3/access/users/{user_id}/llm-model-configs/{config_id} \
  -H "Authorization: Bearer <token>"
```

---

## Error Codes

| Status | Description |
|--------|-------------|
| 200 | Success |
| 201 | Created |
| 204 | Deleted (no content) |
| 400 | Bad request |
| 401 | Unauthorized |
| 404 | Not found |
| **409** | **Conflict (optimistic lock violation)** |
| 500 | Server error |

### 409 Conflict Response

```json
{
  "detail": "Concurrent modification detected. Expected version 5, but current version is 6. Please retry."
}
```

---

## Concurrency Control

### Optimistic Locking

This API uses **optimistic locking** to prevent concurrent modification conflicts:

1. **Version Tracking**: Each configuration has a `version` field that starts at 0 and increments on each update
2. **Read-Modify-Write**: When updating, clients should include the `expected_version` from their last read
3. **Conflict Detection**: If the provided version doesn't match the current version, the update is rejected with HTTP 409

### When to Use Optimistic Locking

**Use `expected_version` when:**
- Multiple users/admins might modify the same configuration
- You want to prevent accidental overwrites of concurrent changes
- Building interactive UIs that display and edit configurations

**Skip `expected_version` when:**
- You're sure no one else is modifying the config
- Performance is more important than data integrity (not recommended)



---

## Security Notes

### API Key Encryption

All API keys are encrypted using Fernet symmetric encryption (AES-128-CBC). Encryption keys are stored in `{secrets_dir}/gns3_encryption_key` with 0600 permissions.

### Access Control

All endpoints require appropriate privileges:
- **User.Audit**: View user configurations
- **User.Modify**: Create, update, delete user configurations
- **Group.Audit**: View group configurations
- **Group.Modify**: Create, update, delete group configurations

### API Key Visibility

The API implements strict API key visibility controls to protect sensitive credentials:

**Security Policy: API keys are NEVER returned via API endpoints**

| Scenario | User Configs | Group Configs |
|----------|-------------|---------------|
| User viewing own configs | **Hidden (null)** | N/A |
| User viewing inherited group configs | N/A | **Hidden (null)** |
| Admin viewing other users' configs | **Hidden (null)** | N/A |
| Viewing group configs directly (with `Group.Audit`) | N/A | **Hidden (null)** |

**Rules:**
1. **All API responses**: `api_key` field is **always set to `null`** in all API responses
2. **Database storage**: API keys are encrypted using Fernet symmetric encryption before storage
3. **Internal use only**: API keys are only decrypted internally by the system (e.g., when the Copilot Agent makes LLM API calls)
4. **Super admins**: Can access the database directly and decrypt any API key using the encryption key - this is by design as super admins have system-level access

**Important Notes:**
- API keys are stored in the database in **encrypted** format using Fernet symmetric encryption
- **No API endpoint returns API keys** - the `api_key` field is always `null` in responses
- API keys can still be **created and updated** via POST/PUT endpoints
- The system internally decrypts API keys when needed (e.g., for making LLM API calls)
- Super admins with database access can retrieve & decrypt any API key - this is intentional and reflects their system-level privileges

**⚠️ Security First Design**
> **API keys are never exposed through the application API.**
>
> - All GET endpoints return `api_key: null`
> - POST/PUT endpoints accept API keys for storage, but responses still return `api_key: null`
> - This prevents API keys from being leaked through logs, browser devtools, or network monitoring
> - API keys are only decrypted internally by the system when making actual LLM API calls
>
> **Design Rationale**: This defense-in-depth approach ensures that even if someone gains access to API logs or responses, they will never find valid API keys.

**Example:**
```json
// User viewing their own configs
{
  "configs": [
    {
      "config_id": "uuid-1",
      "name": "GPT-4",
      "source": "user",
      "config": {
        "api_key": null  // Always hidden, even for own configs
      }
    },
    {
      "config_id": "uuid-2",
      "name": "Claude-3",
      "source": "group",
      "config": {
        "api_key": null  // Always hidden
      }
    }
  ]
}

// Admin viewing another user's configs
{
  "configs": [
    {
      "config_id": "uuid-1",
      "name": "GPT-4",
      "source": "user",
      "config": {
        "api_key": null  // Always hidden
      }
    }
  ]
}

// User with Group.Audit viewing group configs directly
{
  "configs": [
    {
      "config_id": "uuid-3",
      "name": "Gemini Pro",
      "config": {
        "api_key": null  // Always hidden
      }
    }
  ]
}

// Creating a new config (request includes api_key)
POST /users/{user_id}/llm-model-configs
{
  "name": "GPT-4",
  "api_key": "sk-xxxxx"  // Sent in request
}

// Response (api_key is filtered)
{
  "config_id": "uuid-1",
  "name": "GPT-4",
  "config": {
    "api_key": null  // Always null in responses
  }
}
```

---

## Migration from Old User Settings API

The old user settings API (`/v3/access/users/{user_id}/profiles`) stored configurations in the `users.model_configs` JSON column. This new API uses a dedicated table with better inheritance support and optimistic locking.

**Migration strategy:**
1. Run the database migration to create the `llm_model_configs` table
2. Optionally migrate existing data from `users.model_configs` to the new table
3. Update clients to use the new API endpoints
4. Update clients to handle `version` field and 409 Conflict errors
5. Deprecate the old `/profiles` endpoints

**Key differences:**
- **Inheritance**: Users without configs inherit from groups (automatic fallback)
- **Optimistic locking**: New `version` field and `expected_version` parameter
- **Dedicated table**: Better query performance and data integrity
- **Transparent encryption**: API keys auto-encrypted/decrypted by the API
- **Model type support**: New `model_type` field for categorizing models (text, vision, stt, tts, multimodal, embedding, reranking, other)
- **Table-level indexing**: `name` and `model_type` stored as table columns for efficient filtering and querying

---

## Model Type Filtering

The `model_type` table column enables efficient filtering and querying of configurations by model type:

### Common Use Cases

1. **Filter by model type**: Retrieve only text generation models for chat features
2. **Multi-model applications**: Select appropriate model based on task type (text vs vision vs embedding)
3. **Model type analytics**: Query and analyze usage patterns by model type
4. **Type-specific defaults**: Set different default models for different model types

### Example: Filter text models (client-side)

```python
# After fetching configs, filter by model_type
configs = get_user_configs(user_id)
text_models = [c for c in configs if c["model_type"] == "text"]
vision_models = [c for c in configs if c["model_type"] == "vision"]
```

### Database Index

The `model_type` column is indexed for efficient queries:
```sql
CREATE INDEX idx_llm_model_configs_model_type ON llm_model_configs(model_type);
```

This enables fast lookups when filtering by model type, even with large datasets.

---

## Context Limit Configuration

### What is `context_limit`?

The `context_limit` field specifies the maximum context window size for an LLM model. This is a **required field** for all model configurations.

### Why is it required?

Model providers frequently update their models and change context window sizes:
- OpenAI GPT-4o: 128K tokens (may change)
- Anthropic Claude 3.5: 200K tokens (may change)
- Google Gemini 1.5: 2.8M tokens (may change)

Hardcoding these values in the system would quickly become outdated. Requiring users to configure this field ensures that the system always uses the correct, up-to-date values.

### Unit: K tokens

The `context_limit` value is specified in **K tokens** (thousands of tokens) to make it easier to read and write:

| Official Documentation | API Configuration |
|---------------------|-------------------|
| 128,000 tokens | `"context_limit": 128` |
| 200,000 tokens | `"context_limit": 200` |
| 2,800,000 tokens | `"context_limit": 2800` |

### How to find the correct value

1. **Check the official documentation** for your model:
   - OpenAI: https://platform.openai.com/docs/models
   - Anthropic: https://docs.anthropic.com/claude/docs/models-overview
   - Google: https://ai.google.dev/gemini-api/docs/models
   - DeepSeek: https://platform.deepseek.com/api-docs/

2. **Convert from tokens to K**:
   ```
   context_limit = official_value_in_tokens / 1000

   Example:
   GPT-4o: 128,000 tokens / 1000 = 128
   ```

### Example: Common Models

| Model | Official Value | Configuration |
|-------|---------------|--------------|
| GPT-4o | 128,000 | `"context_limit": 128` |
| GPT-3.5 Turbo | 16,385 | `"context_limit": 17` |
| Claude 3.5 Sonnet | 200,000 | `"context_limit": 200` |
| Gemini 1.5 Pro | 2,800,000 | `"context_limit": 2800` |
| DeepSeek Chat | 128,000 | `"context_limit": 128` |

### Context Strategy

The optional `context_strategy` field controls how aggressively the system uses the available context window:

| Strategy | Usage | Best For |
|----------|-------|----------|
| `conservative` | 60% of limit | Long outputs, complex tasks, uncertain output size |
| `balanced` (default) | 75% of limit | Most conversations, general use |
| `aggressive` | 85% of limit | Short outputs, analysis tasks, predictable output size |

### Error Handling

If `context_limit` is missing or invalid, the API will return:

```json
HTTP 400 Bad Request
{
  "detail": "context_limit is required (unit: K tokens, e.g., 128 = 128K = 128,000 tokens). Please check your model provider's documentation for the current context window size and specify it in the configuration."
}
```

---

## Future Enhancements

### Optional `base_url` Field

**Current Behavior:**
The `base_url` field is currently required for all configurations, even for mainstream providers (OpenAI, Anthropic, Google, DeepSeek, xAI) that have well-known, stable endpoints.

**Proposed Enhancement:**
Make `base_url` an optional field that automatically uses provider defaults when not specified.

**Benefits:**
- Simplified configuration for common use cases
- Reduced user error (typos in URLs)
- Better user experience for mainstream providers

**Proposed Implementation:**

1. **Schema Changes** (`gns3server/schemas/controller/llm_model_configs.py`):
   ```python
   # Current
   base_url: str = Field(..., description="API base URL")

   # Proposed
   base_url: Optional[str] = Field(None, description="API base URL (optional, uses provider default if not specified)")
   ```

2. **Model Factory Changes** (`gns3server/agent/gns3_copilot/agent/model_factory.py`):
   - Handle `None` or empty `base_url` by passing it to LangChain's `init_chat_model`
   - LangChain will automatically use the provider's default endpoint

3. **Backward Compatibility:**
   - Existing configurations with explicit `base_url` continue to work
   - No migration required

**Example After Enhancement:**

```json
// Mainstream provider - no base_url needed
{
  "name": "GPT-4o",
  "provider": "openai",
  "model": "gpt-4o",
  "context_limit": 128
}

// Ollama - base_url still required
{
  "name": "Llama-3-Local",
  "provider": "ollama",
  "base_url": "http://localhost:11434",
  "model": "llama3",
  "context_limit": 8
}

// Custom endpoint - base_url specified
{
  "name": "Azure-GPT-4",
  "provider": "openai",
  "base_url": "https://your-resource.openai.azure.com/...",
  "model": "gpt-4",
  "context_limit": 128
}
```

**Implementation Status:** Not yet implemented. Documented for future reference.
