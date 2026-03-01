# User Settings API

## Document Information

| Field | Value |
|-------|-------|
| **Created** | 2026-03-01 |
| **Last Revised** | 2026-03-01 |
| **Version** | 1.0.0 |
| **Status** | Stable |
| **Author** | Guobin Yue |

---

## Changelog

### Version 1.0.0 (2026-03-01)
- Initial release
- Profile-based configuration management
- Single table design (users.model_configs)
- Multi-profile support with active switching
- Extensible field support via JSON storage

---

## Overview

The User Settings API provides a unified and flexible configuration management system. User configurations are stored directly in the `users` table as a JSON field, eliminating the need for separate tables.

---

## Features

### 1. Profile-Based Configuration

Store all user settings as profiles. Each profile represents a complete configuration that can include:
- LLM provider settings
- API credentials
- Model parameters
- Any custom fields via extensible JSON storage

**Use Cases:**
- Multiple LLM configurations for different providers
- Quick switching between work and personal settings
- A/B testing different model parameters
- Custom configurations for specific projects

### 2. Active Profile Management

Users can create multiple profiles and mark one as "active". The system always uses the active profile for operations.

### 3. Extensible Field Support

Beyond core fields, the API accepts any additional custom fields.

---

## Data Storage

### Storage Location

All data is stored in the GNS3 controller database (SQLite):

- **Linux**: `~/.config/GNS3/gns3_controller.db`
- **macOS**: `~/Library/Application Support/GNS3/gns3_controller.db`
- **Windows**: `%APPDATA%\GNS3\gns3_controller.db`

### Storage Structure

Configurations are stored as a JSON field `model_configs` in the `users` table:

```
users table:
┌────────────────────────────────────┐
│ user_id                            │
│ username                           │
│ email                              │
│ ...                                │
│ model_configs (TEXT/JSON)          │
│   {                                │
│     "profiles": [...],             │
│     "active": "profile_name"       │
│   }                                │
└────────────────────────────────────┘
```

This design:
- Eliminates the need for a separate `user_settings` table
- Simplifies queries (no joins required)
- Reduces code complexity
- Maintains flexibility for future fields

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v3/access/users/{user_id}/profiles` | Get all profiles |
| POST | `/v3/access/users/{user_id}/profiles` | Create a new profile |
| PUT | `/v3/access/users/{user_id}/profiles/{name}` | Update a profile |
| DELETE | `/v3/access/users/{user_id}/profiles/{name}` | Delete a profile |
| GET | `/v3/access/users/{user_id}/profiles/active` | Get the active profile |
| PUT | `/v3/access/users/{user_id}/profiles/active` | Set the active profile |

---

## Authentication

All endpoints require JWT authentication:

```
Authorization: Bearer <your_token>
```

Tokens are obtained via `/access/users/login`.

---

## Profile Fields

### Core Fields (Required)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| name | string | Yes | - | Unique profile identifier (1-50 chars) |
| provider | string | No | "openai" | LLM provider name |
| model | string | Yes | - | Model name/identifier |
| api_key | string | Yes | - | API authentication key |
| base_url | string | No | "" | API endpoint URL (empty = use provider default) |
| temperature | string | No | "0.7" | Generation temperature |

### Extended Fields (Optional)

Any additional fields are accepted and stored:

- `max_tokens` - Maximum response tokens
- `top_p` - Nucleus sampling parameter
- `stream` - Enable streaming
- Custom provider-specific fields

### Provider Default URLs

When `base_url` is empty or not provided, the client should use provider-specific defaults:

| Provider | Default Base URL |
|----------|------------------|
| openai | https://api.openai.com/v1 |
| qwen | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| anthropic | https://api.anthropic.com |
| deepseek | https://api.deepseek.com/v1 |
| moonshot | https://api.moonshot.cn/v1 |
| zhipu | https://open.bigmodel.cn/api/paas/v4 |

**Note**: Clients are responsible for applying default URLs when `base_url` is empty.

---

## Usage Examples

### Create a Profile

```bash
curl -X POST "http://localhost:3080/v3/access/users/{user_id}/profiles" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "openai-default",
    "provider": "openai",
    "model": "gpt-4",
    "api_key": "sk-xxx"
  }'
```

Note: `base_url` is optional. If not provided, the client will use the provider's default URL.

### Create a Profile with Custom Base URL

```bash
curl -X POST "http://localhost:3080/v3/access/users/{user_id}/profiles" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "qwen",
    "provider": "qwen",
    "model": "qwen-max",
    "api_key": "sk-xxx",
    "base_url": "https://api.qwen.com/v1",
    "temperature": "0.7",
    "max_tokens": 2000
  }'
```

### Create a Profile with Extended Fields

The API accepts any additional custom fields. These are saved and returned as-is:

```bash
curl -X POST "http://localhost:3080/v3/access/users/{user_id}/profiles" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "deepseek",
    "provider": "deepseek",
    "model": "deepseek-chat",
    "api_key": "sk-xxx",
    "temperature": "0.0",
    "base_url": "https://api.deepseek.com/v1",
    "max_tokens": 4000,
    "top_p": "0.9",
    "custom_field": "custom_value"
  }'
```

**Response:**
```json
{
  "name": "deepseek",
  "provider": "deepseek",
  "model": "deepseek-chat",
  "api_key": "sk-xxx",
  "temperature": "0.0",
  "base_url": "https://api.deepseek.com/v1",
  "max_tokens": 4000,
  "top_p": "0.9",
  "custom_field": "custom_value"
}
```

### Get All Profiles

```bash
curl -X GET "http://localhost:3080/v3/access/users/{user_id}/profiles" \
  -H "Authorization: Bearer <token>"
```

**Response (with profiles):**
```json
{
  "profiles": [
    {
      "name": "qwen",
      "provider": "qwen",
      "model": "qwen-max",
      "api_key": "sk-xxx",
      "base_url": "https://api.qwen.com/v1",
      "temperature": "0.7",
      "max_tokens": 2000
    }
  ],
  "active": "qwen"
}
```

**Response (empty profiles):**
```json
{
  "profiles": [],
  "active": "default"
}
```

### Set Active Profile

```bash
curl -X PUT "http://localhost:3080/v3/access/users/{user_id}/profiles/active" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"profile_name": "qwen"}'
```

### Get Active Profile

```bash
curl -X GET "http://localhost:3080/v3/access/users/{user_id}/profiles/active" \
  -H "Authorization: Bearer <token>"
```

**Response:**
```json
{
  "name": "qwen",
  "provider": "qwen",
  "model": "qwen-max",
  "api_key": "sk-xxx",
  "base_url": "https://api.qwen.com/v1",
  "temperature": "0.7",
  "max_tokens": 2000
}
```

### Update a Profile

```bash
curl -X PUT "http://localhost:3080/v3/access/users/{user_id}/profiles/qwen" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "temperature": "0.9",
    "max_tokens": 4000
  }'
```

### Delete a Profile

```bash
curl -X DELETE "http://localhost:3080/v3/access/users/{user_id}/profiles/qwen" \
  -H "Authorization: Bearer <token>"
```

---

## Error Handling

| Status | Description |
|--------|-------------|
| 200 OK | Request successful |
| 201 Created | Profile created successfully |
| 204 No Content | Deletion successful |
| 400 Bad Request | Invalid data (e.g., duplicate name) |
| 401 Unauthorized | Missing or invalid token |
| 404 Not Found | Profile not found |
| 500 Internal Server Error | Server error |

---

## Design Principles

1. **Simplicity** - Single table design, no complex joins
2. **Flexibility** - JSON storage supports arbitrary fields
3. **Clarity** - Clean, intuitive API endpoints
4. **Reliability** - Proper validation and error handling
5. **Security** - JWT authentication and user isolation

---

## Common Workflows

### Multi-Environment Setup

Create multiple profiles for different environments, then switch between them:

1. Create profiles for each environment (work, personal, etc.)
2. Switch between them using `PUT /profiles/active`

Example:
```bash
# Create work profile → POST /profiles {"name": "work", ...}
# Create personal profile → POST /profiles {"name": "personal", ...}
# Switch to work → PUT /profiles/active {"profile_name": "work"}
```

### Testing Different Parameters

Create test profiles with different configurations, then easily switch:

1. Create a test profile with specific parameters
2. Switch to test profile
3. Switch back to production when done

Example:
```bash
# Create test profile → POST /profiles {"name": "test-high-temp", "temperature": "0.9", ...}
# Switch to test → PUT /profiles/active {"profile_name": "test-high-temp"}
# Switch back → PUT /profiles/active {"profile_name": "production"}
```

---

## Database Schema

### users table (modified)

| Column | Type | Description |
|--------|------|-------------|
| user_id | CHAR(32)/UUID | Primary key |
| username | String | Unique username |
| email | String | Unique email |
| full_name | String | Full name |
| hashed_password | String | Hashed password |
| last_login | DateTime | Last login time |
| is_active | Boolean | Active status |
| is_superadmin | Boolean | Super admin flag |
| **model_configs** | **Text (JSON)** | **Model profiles data** |
| created_at | DateTime | Creation timestamp |
| updated_at | DateTime | Update timestamp |

---

## Database Migration

Automatic migration via Alembic on server startup. Manual commands:

```bash
alembic current        # Check version
alembic upgrade head   # Upgrade to latest
alembic history        # View history
```

The migration adds the `model_configs` column to the existing `users` table.

---

## Integration Guide

### Reading User Profile in Other Modules

```python
from gns3server.db.repositories.users import UsersRepository

# Get active profile for a user
async def get_user_config(user_id: str, users_repo: UsersRepository):
    profile = await users_repo.get_active_model_profile(user_id)
    if profile:
        return {
            "provider": profile["provider"],
            "model": profile["model"],
            "api_key": profile["api_key"],
            "base_url": profile["base_url"],
            "temperature": profile["temperature"],
            # Additional fields...
        }
    return None
```

---

## Best Practices

1. **Use descriptive profile names** - e.g., "work-gpt4", "personal-claude"
2. **Validate API keys** before saving
3. **Keep backups** of important configurations
4. **Test profiles** before using in production
5. **Delete unused profiles** to keep settings organized

---

## Troubleshooting

### Common Issues

**Issue**: "Profile not found" when switching
- **Solution**: List all profiles first to verify the name

**Issue**: "Profile already exists" when creating
- **Solution**: Use a unique name or update the existing profile

**Issue**: No profiles configured
- **Solution**: Create at least one profile before using the API

**Issue**: Authentication fails
- **Solution**: Verify JWT token is valid and not expired

---

## Summary

The User Settings API provides a clean, simple approach to configuration management. By storing configurations directly in the users table as JSON, we achieve:

- **Simpler database schema** - No extra tables needed
- **Better performance** - No joins required
- **Easier maintenance** - Less code to manage
- **Same flexibility** - JSON supports arbitrary fields

This design prioritizes simplicity without sacrificing functionality.

**Key Benefits:**
- Single table design eliminates complexity
- Direct field access improves query performance
- Reduced code means easier maintenance
- JSON storage preserves extensibility
- Clean integration with other modules

---

## Appendix

### Quick Reference Card

```
POST   /v3/access/users/{user_id}/profiles              Create profile
GET    /v3/access/users/{user_id}/profiles              List all profiles
GET    /v3/access/users/{user_id}/profiles/active       Get active profile
PUT    /v3/access/users/{user_id}/profiles/active       Switch active profile
PUT    /v3/access/users/{user_id}/profiles/{name}       Update profile
DELETE /v3/access/users/{user_id}/profiles/{name}       Delete profile
```

### Minimum Required Fields

To create a valid profile, you only need:
- `name` - Profile identifier
- `model` - Model name
- `api_key` - API key

All other fields have sensible defaults or are optional.

---

**Document Version**: 1.0.0
**Last Updated**: 2026-03-01
**Next Review**: 2026-06-01

