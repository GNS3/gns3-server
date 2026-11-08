"""Seed the default ACEs granting the User role to the Users group.

Revision ID: c5e9a3f7d821
Revises: e2a7c9d4b601
"""

import logging
import uuid

import sqlalchemy as sa
from alembic import op

revision = "c5e9a3f7d821"
down_revision = "e2a7c9d4b601"
branch_labels = None
depends_on = None

log = logging.getLogger(__name__)

# keep in sync with create_default_aces in gns3server/db/models/acl.py
DEFAULT_PATHS = ("/projects", "/templates", "/computes", "/symbols", "/appliances", "/images", "/access/users")


def _builtin_ids(connection):

    role_id = connection.execute(sa.text("SELECT role_id FROM roles WHERE name = 'User'")).scalar()
    group_id = connection.execute(sa.text("SELECT user_group_id FROM user_groups WHERE name = 'Users'")).scalar()
    return role_id, group_id


def upgrade():
    """
    Insert the default ACEs on databases created before they were seeded
    at table creation time. Existing ACEs (possibly defined by an admin)
    are never overwritten: each path is only inserted when the "Users"
    group has no ACE on it.
    """

    connection = op.get_bind()
    role_id, group_id = _builtin_ids(connection)
    if role_id is None or group_id is None:
        log.warning("The builtin 'User' role or 'Users' group was not found: skipping the default ACEs migration")
        return

    inserted = 0
    for path in DEFAULT_PATHS:
        existing = connection.execute(
            sa.text("SELECT ace_id FROM acl WHERE group_id = :group_id AND path = :path"),
            {"group_id": group_id, "path": path},
        ).scalar()
        if existing is not None:
            continue
        connection.execute(
            sa.text(
                "INSERT INTO acl (ace_id, ace_type, path, propagate, allowed, role_id, group_id)"
                " VALUES (:ace_id, 'group', :path, 1, 1, :role_id, :group_id)"
            ),
            {"ace_id": uuid.uuid4().hex, "path": path, "role_id": role_id, "group_id": group_id},
        )
        inserted += 1
    log.info(f"Inserted {inserted} default ACE(s) granting the 'User' role to the 'Users' group")


def downgrade():
    """
    Remove the default ACEs. Only rows with the exact default signature are
    deleted: ACEs edited by an admin (different role, propagate or allowed
    flags) are preserved.
    """

    connection = op.get_bind()
    role_id, group_id = _builtin_ids(connection)
    if role_id is None or group_id is None:
        return
    connection.execute(
        sa.text(
            "DELETE FROM acl WHERE group_id = :group_id AND role_id = :role_id AND user_id IS NULL"
            " AND path IN :paths AND propagate = 1 AND allowed = 1"
        ).bindparams(sa.bindparam("paths", expanding=True)),
        {"group_id": group_id, "role_id": role_id, "paths": list(DEFAULT_PATHS)},
    )
