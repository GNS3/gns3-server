# User Settings API

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 2.0.0 | 2026-03-01 | Add API key encryption, optimistic locking, data validation |
| 1.0.0 | 2026-03-01 | Initial release |

---

## Code Changes

### 1. Database Schema

**New columns in `users` table:**

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

- **Algorithm**: Fernet symmetric encryption (AES-128-CBC)
- **Key storage**: `{secrets_dir}/gns3_encryption_key`
- **Key generation**: Auto-generated on first startup, permissions 0600
- **Behavior**: Auto-encrypt on save, auto-decrypt on retrieve

### 3. Optimistic Locking

- `model_configs_version` auto-increments on each update
- Send `expected_version` in write requests for validation
- Returns HTTP 409 if version mismatch

### 4. New Files

| File | Description |
|------|-------------|
| `gns3server/utils/encryption.py` | Encryption utilities |
| `gns3server/db_migrations/versions/20260301_add_model_configs_version.py` | Add version column |
| `gns3server/db_migrations/versions/20260301_validate_model_configs.py` | Validate and repair JSON |

---

## API Endpoints

### Base Path

```
/v3/access/users/{user_id}/profiles
```

### 1. Get All Profiles

**Request**
```
GET /v3/access/users/{user_id}/profiles
Authorization: Bearer <token>
```

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
POST /v3/access/users/{user_id}/profiles
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "qwen",
  "provider": "qwen",
  "model": "qwen-max",
  "api_key": "sk-xxx"
}
```

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
GET /v3/access/users/{user_id}/profiles/active
Authorization: Bearer <token>
```

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
PUT /v3/access/users/{user_id}/profiles/active
Authorization: Bearer <token>
Content-Type: application/json

{
  "profile_name": "qwen",
  "expected_version": 3  // Optional, for optimistic locking
}
```

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
PUT /v3/access/users/{user_id}/profiles/{profile_name}
Authorization: Bearer <token>
Content-Type: application/json

{
  "temperature": "0.9",
  "max_tokens": 4000
}
```

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
DELETE /v3/access/users/{user_id}/profiles/{profile_name}
Authorization: Bearer <token>
```

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
| model | string | Model name |
| api_key | string | API key, auto-encrypted |

### Optional Fields

| Field | Type | Default | Description |
|------|------|---------|-------------|
| provider | string | "openai" | Provider name |
| base_url | string | "" | API endpoint URL |
| temperature | string | "0.7" | Temperature parameter |

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
| 500 | Server error
