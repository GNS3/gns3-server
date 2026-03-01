# Database Migration Issue

## Document Information

| Field | Value |
|-------|-------|
| **Created** | 2026-03-01 |
| **Last Revised** | 2026-03-01 |
| **Version** | 1.0.0 |
| **Status** | Known Issue |
| **Affects** | GNS3 Server 3.1.0.dev1 |

---

## Issue Summary

When upgrading GNS3 Server to versions with Alembic database migrations, existing databases may not have version tracking information, causing the server to skip necessary migrations.

---

## Problem Description

### Background

GNS3 Server uses Alembic for database version management. However, the initial migration (`7ceeddd9c9a8_init`) is empty because tables are created by SQLAlchemy's `Base.metadata.create_all()` rather than through migrations.

### The Issue

When an existing database (created by SQLAlchemy) is first used with a version of GNS3 that has Alembic migrations:

1. The `alembic_version` table is either missing or empty
2. Server detects `current_rev = None`
3. Server assumes this is a **new database**
4. Server marks the database as `head` (latest version)
5. **Migration steps are skipped**
6. New database columns/changes are not applied

### Root Cause

The database connection logic in `gns3server/db/tasks.py`:

```python
if current_rev is None:
    await conn.run_sync(Base.metadata.create_all)
    await conn.run_sync(run_stamp, alembic_cfg)  # Stamps to HEAD
```

This logic assumes `current_rev = None` only happens for brand new databases, but it can also happen for:
- Existing databases created by older GNS3 versions
- Databases where the `alembic_version` table was lost or corrupted

---

## Affected Scenarios

### Scenario 1: Old Database Without Version Tracking

**Condition:**
- Database has all tables (users, projects, templates, etc.)
- `alembic_version` table is missing or empty

**Result:**
- Database is stamped to `head`
- Pending migrations are skipped
- New features fail due to missing columns

### Scenario 2: Fresh Installation

**Condition:**
- Database does not exist yet
- Or database exists but is completely empty

**Result:**
- Works correctly
- All tables are created
- Stamped to `head`

---

## Impact

### Symptoms

1. **Missing column errors**
   ```
   sqlite3.OperationalError: no such column: users.model_configs
   ```

2. **Migration not applied**
   New database schema changes are not applied to existing databases

3. **Inconsistent behavior**
   - Fresh installations work fine
   - Upgrades from older versions fail

### Who Is Affected

- Users upgrading from GNS3 Server versions before Alembic integration
- Users with databases created by SQLAlchemy `metadata.create_all()`
- Development databases

---

## Workaround

### Temporary Solution

Manually stamp the database to the correct pre-migration version:

```bash
# 1. Stop GNS3 Server

# 2. Stamp database to version before the new migration
sqlite3 ~/.config/GNS3/3.0/gns3_controller.db \
  "INSERT INTO alembic_version (version_num) VALUES ('98083573d011');"

# 3. Restart GNS3 Server
gns3server
```

The server will now detect that the database version is not `head` and automatically run the pending migrations.

### How to Determine the Correct Version

1. Check the migration chain in `gns3server/db_migrations/versions/`:
   ```
   7ceeddd9c9a8_init → 9a5292aa4389 → 98083573d011 → 20260301_add_model_configs
   ```

2. Identify the version before your new migration

3. Stamp to that version and let the server upgrade automatically

---

## Permanent Solution

### Proposed Fix

Modify `gns3server/db/tasks.py` to distinguish between:
- **Truly new databases** (no tables exist)
- **Old databases without version tracking** (tables exist, no version)

```python
if current_rev is None:
    # Check if this is a new or old database
    tables_exist = await conn.run_sync(check_if_tables_exist)

    if tables_exist:
        # Old database without version tracking
        # Stamp to appropriate version and upgrade
        await conn.run_sync(run_stamp, alembic_cfg, "98083573d011")
        await conn.run_sync(run_upgrade, alembic_cfg)
    else:
        # Brand new database
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(run_stamp, alembic_cfg)
```

### Implementation Status

- [ ] Code change proposed
- [ ] Awaiting review
- [ ] Not yet implemented

---

## Prevention

### For Developers

When adding new migrations:

1. **Document the upgrade path** for existing databases
2. **Test migration scenarios**:
   - Fresh installation
   - Upgrade from previous version
   - Old database without version tracking
3. **Provide migration scripts** if automatic migration fails

### For Users

Before upgrading GNS3 Server:

1. **Backup your database**
   ```bash
   cp ~/.config/GNS3/3.0/gns3_controller.db ~/.config/GNS3/3.0/gns3_controller.db.backup
   ```

2. **Check current version**
   ```bash
   sqlite3 ~/.config/GNS3/3.0/gns3_controller.db "SELECT version_num FROM alembic_version;"
   ```

3. **If empty or missing**, follow the workaround above

---

## Related Issues

- **Migration**: `20260301_add_model_configs` - Adds `model_configs` column to users table
- **Base migration**: `7ceeddd9c9a8_init` - Empty init migration
- **Previous migration**: `98083573d011` - Adds tags field to templates

---

## Technical Details

### Migration Chain

```
7ceeddd9c9a8 (init - empty)
    ↓
9a5292aa4389 (add_mac_address_field_in_docker_templates)
    ↓
98083573d011 (add_tags_field_to_templates)
    ↓
20260301_add_model_configs (adds model_configs to users)
    ↓
[HEAD]
```

### Database Detection Logic

Current implementation in `connect_to_db()`:

```python
current_rev, head_rev = await conn.run_sync(check_revision, alembic_cfg)

if current_rev is None:
    # Ambiguous: could be new OR old database
    await conn.run_sync(Base.metadata.create_all)
    await conn.run_sync(run_stamp, alembic_cfg)  # Stamps to HEAD
```

**Issue**: Does not distinguish between new and old databases.

---

## Example Error Messages

```
2026-03-01 13:56:22 ERROR gns3server.api.server:199 Controller database error:
(sqlite3.OperationalError) no such column: users.model_configs

[SQL: SELECT users.user_id, users.username, ... users.model_configs ...
FROM users WHERE users.username = ?]
```

This error occurs because:
1. Database was stamped to `head` automatically
2. The migration that adds `model_configs` was skipped
3. Code tries to access the non-existent column

---

## Testing

### How to Reproduce

1. Create a database using SQLAlchemy `Base.metadata.create_all()`
2. Don't create or populate `alembic_version` table
3. Start GNS3 Server
4. Observe that migrations are skipped

### Expected Behavior

Server should:
1. Detect that tables exist but there's no version
2. Stamp to the appropriate version
3. Run pending migrations

### Actual Behavior

Server:
1. Detects `current_rev = None`
2. Stamps to `head` immediately
3. Skips all migrations

---

## References

- **File**: `gns3server/db/tasks.py` - Database connection and migration logic
- **File**: `gns3server/db_migrations/versions/` - Migration scripts
- **Documentation**: [Alembic Documentation](https://alembic.sqlalchemy.org)

---

## Changelog

### 2026-03-01
- Initial documentation of this issue
- Added workaround and permanent solution proposal
- Documented migration chain and technical details
