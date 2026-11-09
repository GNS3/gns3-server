"""Add the Notification.Audit privilege.

The global controller notification stream (HTTP and WebSocket) used to be
available to any authenticated user and carried every controller event,
including host statistics in the ping notifications. It is now gated by the
Notification.Audit privilege. No default ACE carries it, so by default only
superadmins (who bypass the privilege checks) receive the stream.

The privilege is attached to the built-in "Administrator" role to match new
databases, where that role automatically receives every privilege. A user
holding the role still needs an ACE on /notifications (or /) to reach the
stream.

Revision ID: c8d4b6e2f913
Revises: b5f3a8c1d902
"""

import logging
import uuid

import sqlalchemy as sa
from alembic import op

revision = "c8d4b6e2f913"
down_revision = "b5f3a8c1d902"
branch_labels = None
depends_on = None

log = logging.getLogger(__name__)

# keep in sync with create_default_roles in gns3server/db/models/privileges.py
PRIVILEGE_NAME = "Notification.Audit"
PRIVILEGE_DESCRIPTION = "Receive global controller notifications"


def upgrade():
    """
    Insert the privilege when missing and attach it to the "Administrator"
    role. Administrators keep every privilege, exactly like on a new database.
    """

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO privileges (privilege_id, name, description)"
            " SELECT :privilege_id, :name, :description"
            " WHERE NOT EXISTS (SELECT 1 FROM privileges WHERE name = :name)"
        ),
        {"privilege_id": uuid.uuid4().hex, "name": PRIVILEGE_NAME, "description": PRIVILEGE_DESCRIPTION},
    )
    result = connection.execute(
        sa.text(
            "INSERT INTO privilege_role_map (privilege_id, role_id)"
            " SELECT p.privilege_id, r.role_id FROM privileges p, roles r"
            " WHERE p.name = :name AND r.name = 'Administrator'"
            " AND NOT EXISTS ("
            " SELECT 1 FROM privilege_role_map m WHERE m.privilege_id = p.privilege_id AND m.role_id = r.role_id)"
        ),
        {"name": PRIVILEGE_NAME},
    )
    log.info(f"Added the '{PRIVILEGE_NAME}' privilege and attached it to {result.rowcount} 'Administrator' role(s)")


def downgrade():
    """
    Remove the role attachment, then the privilege. Custom roles an
    administrator built around it are left as they are.
    """

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM privilege_role_map WHERE privilege_id ="
            " (SELECT privilege_id FROM privileges WHERE name = :name)"
        ),
        {"name": PRIVILEGE_NAME},
    )
    connection.execute(sa.text("DELETE FROM privileges WHERE name = :name"), {"name": PRIVILEGE_NAME})
    log.info(f"Removed the '{PRIVILEGE_NAME}' privilege")
