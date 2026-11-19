"""Add the Project.Share and Project.Distribute privileges.

Sharing and distributing a project authorize other users on it (a share
grants access to the very project, a distribution creates copies owned by
the recipients and freezes the source as a template), so they get their own
privileges instead of riding on Project.Audit. The built-in "Lab member"
role deliberately does not receive them: a shared user or a distributed
copy recipient must not pass the lab on to anyone else.

Revision ID: c9e4f7a2b6d8
Revises: f6d3a9c2e8b1
"""

import logging
import uuid

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c9e4f7a2b6d8"
down_revision = "f6d3a9c2e8b1"
branch_labels = None
depends_on = None

log = logging.getLogger(__name__)

# keep in sync with create_default_roles in gns3server/db/models/privileges.py
PRIVILEGES = (
    ("Project.Share", "Share a project with other users or groups"),
    ("Project.Distribute", "Distribute a project as a frozen template"),
)
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
