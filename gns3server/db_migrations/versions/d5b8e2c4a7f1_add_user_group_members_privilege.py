"""Add the User.GroupMembers privilege.

A user who can share or distribute a project needs the recipient names.
User.GroupMembers shows the members of the user's own groups — enough to
fill a share dialog, without the full user list (that stays User.Audit).

Revision ID: d5b8e2c4a7f1
Revises: c9e4f7a2b6d8
"""

import logging
import uuid

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d5b8e2c4a7f1"
down_revision = "c9e4f7a2b6d8"
branch_labels = None
depends_on = None

log = logging.getLogger(__name__)

# keep in sync with create_default_roles in gns3server/db/models/privileges.py
PRIVILEGES = (("User.GroupMembers", "List the members of your own user groups"),)
ROLE_NAMES = ("Administrator", "User")


def _add_privileges(connection, privileges, role_names) -> None:
    """
    Insert each privilege when missing and attach it to the given built-in
    roles when missing, exactly like on a new database. Objects an
    administrator customized are never overwritten.
    """

    for name, description in privileges:
        connection.execute(
            sa.text(
                "INSERT INTO privileges (privilege_id, name, description)"
                " SELECT :privilege_id, :name, :description"
                " WHERE NOT EXISTS (SELECT 1 FROM privileges WHERE name = :name)"
            ),
            {"privilege_id": uuid.uuid4().hex, "name": name, "description": description},
        )
        result = connection.execute(
            sa.text(
                "INSERT INTO privilege_role_map (privilege_id, role_id)"
                " SELECT p.privilege_id, r.role_id FROM privileges p, roles r"
                " WHERE p.name = :name AND r.name IN :roles"
                " AND NOT EXISTS ("
                " SELECT 1 FROM privilege_role_map m WHERE m.privilege_id = p.privilege_id AND m.role_id = r.role_id)"
            ).bindparams(sa.bindparam("roles", expanding=True)),
            {"name": name, "roles": list(role_names)},
        )
        log.info(f"Added the '{name}' privilege and attached it to {result.rowcount} role(s)")


def _remove_privileges(connection, privilege_names) -> None:
    """
    Remove the role attachments, then the privileges. Custom roles an
    administrator built around them are left as they are.
    """

    for name in privilege_names:
        connection.execute(
            sa.text(
                "DELETE FROM privilege_role_map WHERE privilege_id ="
                " (SELECT privilege_id FROM privileges WHERE name = :name)"
            ),
            {"name": name},
        )
        connection.execute(sa.text("DELETE FROM privileges WHERE name = :name"), {"name": name})
        log.info(f"Removed the '{name}' privilege")


def upgrade() -> None:

    _add_privileges(op.get_bind(), PRIVILEGES, ROLE_NAMES)


def downgrade() -> None:

    _remove_privileges(op.get_bind(), (name for name, _ in PRIVILEGES))
