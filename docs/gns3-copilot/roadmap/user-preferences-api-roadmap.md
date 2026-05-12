<!--
SPDX-License-Identifier: CC-BY-SA-4.0
See LICENSE file for licensing information.
-->

> This document is a roadmap/planning document. The described features have not been implemented yet.


# User Preferences API — Roadmap

## Problem

Currently, user-specific preferences (UI theme, language, AI Copilot settings, workspace layout, etc.) can only be stored in browser `localStorage`. This has several drawbacks:

1. **localStorage clearing** — clearing browser data or switching devices loses all settings
2. **No cross-device sync** — users must reconfigure preferences on each device
3. **No API access** — CLI tools and third-party clients cannot read/write preferences
4. **Fragile persistence** — localStorage can be cleared by browser maintenance or incognito mode

## Proposed API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v3/access/users/me/preferences` | Get all preferences for current user |
| `PUT` | `/v3/access/users/me/preferences` | Merge preferences (top-level merge, not replace) |
| `DELETE` | `/v3/access/users/me/preferences` | Clear all preferences |

### Storage

A `preferences` JSON column on the existing `users` table:

- Type: `JSON`, non-nullable, default `'{}'`
- No schema enforcement — clients can store arbitrary key-value pairs
- Examples: `{"theme": "dark", "language": "zh-CN", "copilot_default_mode": "teaching_assistant"}`

### Implementation Plan

1. Add `preferences` JSON column to `User` ORM model
2. Create Alembic migration
3. Add `UserPreferencesUpdate` Pydantic schema with `extra="allow"`
4. Add `get_user_preferences()` and `update_user_preferences()` to `UsersRepository`
5. Add three endpoints to `users.py` router: `GET/PUT/DELETE /me/preferences`

### Related Files

| File | Role |
|------|------|
| `gns3server/db/models/user.py` | User ORM model |
| `gns3server/db/repositories/users.py` | UsersRepository with database operations |
| `gns3server/api/routes/controller/users.py` | User API router |
| `gns3server/schemas/` | Pydantic schemas |
| `gns3server/db/versions/` | Alembic migrations |

## Status

- [ ] Add `preferences` JSON column to User ORM model
- [ ] Create Alembic migration
- [ ] Add `UserPreferencesUpdate` schema
- [ ] Add repository methods
- [ ] Add API endpoints to users.py router
