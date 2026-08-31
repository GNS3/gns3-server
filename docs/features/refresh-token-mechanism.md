# Stateless JWT Refresh Token Mechanism

## Overview

GNS3 server now supports a stateless JWT refresh token mechanism for interactive sessions (e.g., Web UI). This allows clients to stay authenticated across page reloads without repeated username/password prompts, while keeping access tokens short-lived.

No new database table or migration is required — refresh tokens are signed JWTs using the same secret and algorithm as access tokens.

## Architecture

```mermaid
graph TD
    Client -->|login / authenticate| API[Controller API]
    API -->|access_token + refresh_token| Client
    Client -->|POST /refresh| Refresh[Refresh Endpoint]
    Refresh -->|new access_token + new refresh_token| Client
    Client -->|Bearer access_token| Protected[Protected Endpoints]
    Protected -->|401| Client
    Client -->|refresh_token in body| Refresh
    Refresh -->|401 if invalid/expired/revoked| Client
    Refresh -->|verify type, exp, ver| AuthService[AuthService]
    AuthService -->|check token_version| DB[(users table)]
```

## Business Process

### Login / Authenticate Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant API as Controller API
    participant AS as AuthService
    participant DB as Database

    C->>API: POST /login or /authenticate (username + password)
    API->>DB: authenticate_user()
    DB-->>API: user (with token_version)
    API->>AS: create_access_token(user, ver)
    API->>AS: create_refresh_token(user, ver)
    AS-->>API: access_token (type: access, exp: 15min)
    AS-->>API: refresh_token (type: refresh, exp: 30d)
    API-->>C: { access_token, token_type, refresh_token }
```

### Refresh Flow (Silent Renewal)

```mermaid
sequenceDiagram
    participant C as Client
    participant API as Controller API
    participant AS as AuthService
    participant DB as Database

    Note over C: access_token expired
    C->>API: POST /refresh { refresh_token }
    API->>AS: get_token_data(refresh_token)
    AS-->>API: { username, ver, token_use: "refresh" }
    API->>DB: get_user_by_username()
    DB-->>API: user (with current token_version)
    Note over API,DB: rejects if user not found, inactive, or token_version mismatch
    API->>AS: create_access_token(user, ver)
    API->>AS: create_refresh_token(user, ver)
    AS-->>API: new access_token (sliding window)
    AS-->>API: new refresh_token (sliding window)
    API-->>C: { access_token, token_type, refresh_token }
    C->>API: Retry original request with new access_token
```

### Logout — Token Revocation

```mermaid
sequenceDiagram
    participant C as Client
    participant API as Controller API
    participant DB as Database

    C->>API: POST /logout (Bearer access_token)
    API->>DB: logout_user(user_id) → token_version += 1
    DB-->>API: done
    API-->>C: 204 No Content
    Note over C, DB: All existing access and refresh tokens with old ver are now invalid
```

## API Endpoints

| Method | Path | Description | Authentication |
|--------|------|-------------|---------------|
| POST | `/v3/access/users/login` | Login with form data, returns access + refresh tokens | Public |
| POST | `/v3/access/users/authenticate` | Login with JSON, returns access + refresh tokens | Public |
| POST | `/v3/access/users/refresh` | Exchange a refresh token for a new access token + refresh token | Public (token itself proves identity) |
| POST | `/v3/access/users/logout` | Revoke all tokens for the current user | Bearer token required |

### POST /v3/access/users/refresh

**Request:**
```json
{
  "refresh_token": "<refresh_token>"
}
```

**Response 200:**
```json
{
  "access_token": "<new_access_token>",
  "token_type": "bearer",
  "refresh_token": "<new_refresh_token>"
}
```

**Error Responses:**
- `401` — Invalid, expired, or revoked refresh token
- `422` — Missing `refresh_token` field in request body

## Security Design

### Token Claims

| Claim | Access Token | Refresh Token |
|-------|-------------|---------------|
| `sub` | username | username |
| `exp` | 24h (configurable) | 30d (configurable) |
| `ver` | user's `token_version` | user's `token_version` |
| `type` | `"access"` | `"refresh"` |

### Key Security Properties

- **Type-based isolation**: Access tokens (`type: access`) are rejected by `/refresh`. Refresh tokens (`type: refresh`) are rejected by HTTP and WebSocket authentication paths. This prevents a stolen long-lived refresh token from being used directly for API access.
- **Token version integration**: Both token types carry the user's `token_version`. `logout` increments `token_version` in the database, immediately invalidating all outstanding access and refresh tokens.
- **Stateless (no replay detection)**: Since there is no `refresh_tokens` database table, a stolen refresh token remains valid until its `exp` or until the user logs out. This is an accepted trade-off for avoiding a new table and migration.
- **Sliding window**: Each `/refresh` call issues a new refresh token with a fresh expiry, keeping active sessions alive indefinitely until logout or inactivity.

### Implementation Files

- `gns3server/services/authentication.py` — `_create_token`, `create_access_token`, `create_refresh_token`, `get_token_data`
- `gns3server/api/routes/controller/users.py` — `refresh_access_token` endpoint handler
- `gns3server/api/routes/controller/dependencies/authentication.py` — `_reject_refresh_token` guard in HTTP and WebSocket paths
- `gns3server/schemas/controller/tokens.py` — `Token`, `TokenData`, `RefreshTokenRequest` models
- `gns3server/schemas/config.py` — `jwt_refresh_token_expire_minutes` configuration

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `Controller.jwt_access_token_expire_minutes` | 1440 (24h) | Access token TTL. Web UI recommends 15 min. |
| `Controller.jwt_refresh_token_expire_minutes` | 43200 (30d) | Refresh token TTL. |
| `Controller.jwt_secret_key` | (random) | HMAC signing key for all JWT tokens. |

## Notes

- **Web UI integration**: The client should implement a response interceptor that catches 401, silently calls `/refresh`, and retries the original request. Multiple concurrent 401s should be queued with a single refresh request.
- **No per-session revocation**: All tokens for a user share the same `token_version`. Logout revokes everything. Per-session granularity would require adding a `refresh_tokens` table.
- **Rate limiting**: `/refresh` is a public endpoint with a valid credential (the refresh token). Rate limiting is recommended if brute-force attacks are a concern.
