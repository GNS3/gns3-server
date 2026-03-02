# Group Settings API

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-03 | Initial release - match user settings API functionality |

---

## Code Changes

### 1. Database Schema

**New columns in `user_groups` table:**

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `model_configs` | TEXT | NULL | JSON config data, API keys auto-encrypted |
| `model_configs_version` | INTEGER | 0 | Optimistic locking version |

**Data format:**
```json
{
  "profiles": [
    {
      "name": "profile-name",
      "provider": "openai",
      "model": "gpt-4",
      "api_key": "<encrypted>",
      "base_url": "",
      "temperature": "0.7"
    }
  ],
  "active": "profile-name"
}
```

### 2. Encryption

- **Algorithm**: Fernet symmetric encryption (AES-128-CBC) with URL-safe base64 encoding
- **Key storage**: `{secrets_dir}/gns3_encryption_key` (default: `{config_dir}/gns3_encryption_key`)
- **Key generation**: Auto-generated on first startup, permissions 0600
- **Key priority**: Key file overrides config file settings
- **Validation**: Checks for Fernet prefix (`gAAAAA`) before decryption
- **Behavior**: Auto-encrypt on save, auto-decrypt on retrieve

### 3. Configuration & Keys

**Key file priority**: Key files take precedence over config file settings
- `gns3_jwt_secret_key` - JWT authentication key
- `gns3_encryption_key` - API key encryption key

**Auto-generation**:
- Keys are auto-generated on first startup if files don't exist
- Works even without `gns3_server.conf` configuration file
- Keys persist across server restarts

**Config file**:
- Optional - server uses code defaults if not found
- Default location: `~/.config/GNS3/3.1/gns3_server.conf`
- Key settings in config are overridden by key files

### 4. Database Migration

**For new installations**: The columns are created automatically when the database is initialized.

**For existing installations**: A database migration script will be provided to add the new columns to existing `user_groups` tables.

### 5. Optimistic Locking

- `model_configs_version` auto-increments on each update
- Send `expected_version` in write requests for validation
- Returns HTTP 409 if version mismatch

### 6. Modified Files

| File | Description |
|------|-------------|
| `gns3server/db/models/users.py` | Added `model_configs` and `model_configs_version` to UserGroup |
| `gns3server/db/repositories/users.py` | Added group model config methods |
| `gns3server/api/routes/controller/groups.py` | Added group profile endpoints |

---

## API Endpoints

### Overview

| Method | Path                              | Privilege      |
|--------|-----------------------------------|----------------|
| GET    | /groups/{group_id}/profiles        | Group.Audit    |
| POST   | /groups/{group_id}/profiles        | Group.Modify   |
| GET    | /groups/{group_id}/profiles/active | Group.Audit    |
| PUT    | /groups/{group_id}/profiles/active | Group.Modify   |
| PUT    | /groups/{group_id}/profiles/{name} | Group.Modify   |
| DELETE | /groups/{group_id}/profiles/{name} | Group.Modify   |

### Base Path

```
/v3/access/groups/{user_group_id}/profiles
```

### 1. Get All Profiles

**Request**
```
GET /v3/access/groups/{user_group_id}/profiles
Authorization: Bearer <token>
```

**Required Privilege**: `Group.Audit`

**Response**
```json
{
  "profiles": [
    {
      "name": "openai",
      "provider": "openai",
      "model": "gpt-4",
      "api_key": "sk-xxx",
      "base_url": "",
      "temperature": "0.7"
    }
  ],
  "active": "openai",
  "version": 3
}
```

### 2. Create Profile

**Request**
```
POST /v3/access/groups/{user_group_id}/profiles
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "qwen",
  "provider": "qwen",
  "model": "qwen-max",
  "api_key": "sk-xxx"
}
```

**Required Privilege**: `Group.Modify`

**Response**
```
HTTP Status: 201 Created

{
  "name": "qwen",
  "provider": "qwen",
  "model": "qwen-max",
  "api_key": "sk-xxx",
  "base_url": "",
  "temperature": "0.7"
}
```

### 3. Get Active Profile

**Request**
```
GET /v3/access/groups/{user_group_id}/profiles/active
Authorization: Bearer <token>
```

**Required Privilege**: `Group.Audit`

**Response**
```json
{
  "name": "openai",
  "provider": "openai",
  "model": "gpt-4",
  "api_key": "sk-xxx",
  "base_url": "",
  "temperature": "0.7"
}
```

### 4. Set Active Profile

**Request**
```
PUT /v3/access/groups/{user_group_id}/profiles/active
Authorization: Bearer <token>
Content-Type: application/json

{
  "profile_name": "qwen",
  "expected_version": 3  // Optional, for optimistic locking
}
```

**Required Privilege**: `Group.Modify`

**Response**
```json
{
  "profiles": [...],
  "active": "qwen",
  "version": 4
}
```

**Error Response (Conflict)**
```
HTTP Status: 409 Conflict

{
  "detail": "Concurrent modification detected. Expected version 3, but current version is 5. Please retry."
}
```

### 5. Update Profile

**Request**
```
PUT /v3/access/groups/{user_group_id}/profiles/{profile_name}
Authorization: Bearer <token>
Content-Type: application/json

{
  "temperature": "0.9",
  "max_tokens": 4000
}
```

**Required Privilege**: `Group.Modify`

**Response**
```json
{
  "name": "qwen",
  "provider": "qwen",
  "model": "qwen-max",
  "api_key": "sk-xxx",
  "base_url": "",
  "temperature": "0.9",
  "max_tokens": 4000
}
```

### 6. Delete Profile

**Request**
```
DELETE /v3/access/groups/{user_group_id}/profiles/{profile_name}
Authorization: Bearer <token>
```

**Required Privilege**: `Group.Modify`

**Response**
```
HTTP Status: 204 No Content
```

---

## Field Definitions

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| name | string | Profile name, 1-50 chars, "active" reserved |
| provider | string | Provider name |
| model | string | Model name |
| api_key | string | API key, auto-encrypted |
| base_url | string | API endpoint URL |
| temperature | string | Temperature parameter |

### Extended Fields

Any custom fields supported, e.g., `max_tokens`, `top_p`, `stream`, etc.

---

## Error Codes

| Status | Description |
|--------|-------------|
| 200 | Success |
| 201 | Created |
| 204 | Deleted (no content) |
| 400 | Bad request (duplicate name, reserved name) |
| 401 | Unauthorized |
| 404 | Not found |
| 409 | Conflict (version mismatch) |
| 500 | Server error |

---

## Notes

### Built-in Groups

Built-in groups (like "Administrators" and "Users") can have model configs configured, but their `is_builtin` flag cannot be changed.
