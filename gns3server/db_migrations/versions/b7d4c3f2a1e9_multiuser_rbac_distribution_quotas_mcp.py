"""Multi-user RBAC, distribution, quotas and MCP whitelist schema.

Consolidated migration covering the multi-user work shipped together:

- seed the default ACEs granting the User role to the Users group (and stop
  the seeded /projects ACE from propagating to the projects themselves, so
  projects are private to their creator until shared);
- add the Notification.Audit, Server.Audit, Server.Modify, Link.Marker and
  Project.Marker privileges and attach them to the built-in roles that
  should hold them;
- add the Project.Duplicate, Project.Export, Project.Share, Project.Distribute
  and User.GroupMembers privileges and attach them to the Administrator and
  User roles only: a shared user or a distributed-copy recipient must not
  pass the lab on, and a copy must not be duplicated or exported (its disks
  can be thin overlays of the template project);
- add the built-in "Lab member" role (the default role for distributed lab
  copies) with its project-scoped privileges;
- add the user_preferences, distribution_records and mcp_tool_whitelist
  tables, and the /distributions default ACE;
- add the per-user and per-group node quota columns.

Every step is idempotent and only touches rows with the exact built-in
signature: objects an administrator customized are never overwritten.

Revision ID: b7d4c3f2a1e9
Revises: e2a7c9d4b601
"""

import logging
import uuid

import sqlalchemy as sa
from alembic import op

import gns3server.db.models.base as models

# revision identifiers, used by Alembic.
revision = "b7d4c3f2a1e9"
down_revision = "e2a7c9d4b601"
branch_labels = None
depends_on = None

log = logging.getLogger(__name__)

# keep in sync with create_default_aces in gns3server/db/models/acl.py
DEFAULT_PATHS = ("/projects", "/templates", "/computes", "/symbols", "/appliances", "/images", "/access/users")
DISTRIBUTIONS_PATH = "/distributions"

# keep in sync with create_default_roles in gns3server/db/models/privileges.py
NOTIFICATION_PRIVILEGE = ("Notification.Audit", "Receive global controller notifications")
SERVER_PRIVILEGES = (
    ("Server.Audit", "View server settings"),
    ("Server.Modify", "Update server settings"),
)
MARKER_PRIVILEGES = (
    ("Link.Marker", "Manage traffic markers on a link"),
    ("Project.Marker", "Manage project-level marker definitions"),
)
MARKER_ROLE_NAMES = ("Administrator", "User", "Lab member")

# keep in sync with create_default_roles in gns3server/db/models/privileges.py
# these leave the project scope (a copy lives elsewhere, an archive travels
# off the server) or authorize other users on the project, and listing group
# members is needed to fill the share dialog: the built-in "Lab member" role
# deliberately does not receive them
PROJECT_ACTION_PRIVILEGES = (
    ("Project.Duplicate", "Duplicate a project"),
    ("Project.Export", "Export a project as a portable archive"),
    ("Project.Share", "Share a project with other users or groups"),
    ("Project.Distribute", "Distribute a project as a frozen template"),
    ("User.GroupMembers", "List the members of your own user groups"),
)
PROJECT_ACTION_ROLE_NAMES = ("Administrator", "User")

# keep in sync with add_privileges_to_default_roles in gns3server/db/models/privileges.py
LAB_MEMBER_ROLE_NAME = "Lab member"
LAB_MEMBER_ROLE_DESCRIPTION = "Role for users who received a distributed lab project"
LAB_MEMBER_PRIVILEGES = (
    "Project.Allocate",
    "Project.Audit",
    "Snapshot.Audit",
    "Snapshot.Restore",
    "Node.Audit",
    "Node.Console",
    "Node.PowerMgmt",
    "Link.Audit",
    "Link.Capture",
    "Drawing.Audit",
)

_USER_QUOTA_COLUMNS = ("max_nodes", "max_running_nodes")
_GROUP_QUOTA_COLUMNS = ("default_max_nodes", "default_max_running_nodes")


def _seed_default_aces(connection) -> None:
    """
    Insert the default ACEs on databases created before they were seeded
    at table creation time. Existing ACEs (possibly defined by an admin)
    are never overwritten: each path is only inserted when the "Users"
    group has no ACE on it.
    """

    role_id = connection.execute(sa.text("SELECT role_id FROM roles WHERE name = 'User'")).scalar()
    group_id = connection.execute(sa.text("SELECT user_group_id FROM user_groups WHERE name = 'Users'")).scalar()
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


def _remove_default_aces(connection) -> None:
    """
    Remove the default ACEs. Only rows with the exact default signature are
    deleted: ACEs edited by an admin (different role, propagate or allowed
    flags) are preserved.
    """

    role_id = connection.execute(sa.text("SELECT role_id FROM roles WHERE name = 'User'")).scalar()
    group_id = connection.execute(sa.text("SELECT user_group_id FROM user_groups WHERE name = 'Users'")).scalar()
    if role_id is None or group_id is None:
        return
    connection.execute(
        sa.text(
            "DELETE FROM acl WHERE group_id = :group_id AND role_id = :role_id AND user_id IS NULL"
            " AND path IN :paths AND propagate = 1 AND allowed = 1"
        ).bindparams(sa.bindparam("paths", expanding=True)),
        {"group_id": group_id, "role_id": role_id, "paths": list(DEFAULT_PATHS)},
    )


# keep in sync with create_default_aces in gns3server/db/models/acl.py
_RESTRICT_PROJECTS_ACE = sa.text(
    "UPDATE acl SET propagate = :new_value"
    " WHERE path = '/projects' AND user_id IS NULL AND allowed = 1 AND propagate = :old_value"
    " AND group_id = (SELECT user_group_id FROM user_groups WHERE name = 'Users')"
    " AND role_id = (SELECT role_id FROM roles WHERE name = 'User')"
)


def _restrict_default_projects_ace(connection) -> None:
    """
    Stop the seeded /projects ACE from propagating to the projects, so a
    project is private to its creator until it is explicitly shared. An ACE
    an administrator customized is left untouched.
    """

    result = connection.execute(_RESTRICT_PROJECTS_ACE, {"new_value": 0, "old_value": 1})
    log.info(f"Restricted {result.rowcount} default /projects ACE(s) to the project collection")


def _restore_default_projects_ace(connection) -> None:
    """
    Restore the old propagating default ACE.
    """

    result = connection.execute(_RESTRICT_PROJECTS_ACE, {"new_value": 1, "old_value": 0})
    log.info(f"Restored {result.rowcount} default /projects ACE(s) to the propagating shape")


def _add_privileges(connection, privileges, role_names) -> None:
    """
    Insert each privilege when missing and attach it to the given built-in
    roles when missing, exactly like on a new database.
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


def _add_lab_member_role(connection) -> None:
    """
    Insert the role when missing and attach its privileges. A role already
    bearing the name keeps its identity; the privileges are attached when
    missing, exactly like for the built-in roles on a new database.
    """

    connection.execute(
        sa.text(
            "INSERT INTO roles (role_id, name, description, is_builtin)"
            " SELECT :role_id, :name, :description, 1"
            " WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = :name)"
        ),
        {"role_id": uuid.uuid4().hex, "name": LAB_MEMBER_ROLE_NAME, "description": LAB_MEMBER_ROLE_DESCRIPTION},
    )
    result = connection.execute(
        sa.text(
            "INSERT INTO privilege_role_map (privilege_id, role_id)"
            " SELECT p.privilege_id, r.role_id FROM privileges p, roles r"
            " WHERE r.name = :role AND p.name IN :privileges"
            " AND NOT EXISTS ("
            " SELECT 1 FROM privilege_role_map m WHERE m.privilege_id = p.privilege_id AND m.role_id = r.role_id)"
        ).bindparams(sa.bindparam("privileges", expanding=True)),
        {"role": LAB_MEMBER_ROLE_NAME, "privileges": list(LAB_MEMBER_PRIVILEGES)},
    )
    log.info(f"Added the '{LAB_MEMBER_ROLE_NAME}' role with {result.rowcount} privilege(s)")


def _remove_lab_member_role(connection) -> None:
    """
    Remove the role. The privilege_role_map rows follow the foreign key
    cascade; ACEs referencing the role are left to the administrator.
    """

    connection.execute(sa.text("DELETE FROM roles WHERE name = :name"), {"name": LAB_MEMBER_ROLE_NAME})
    log.info(f"Removed the '{LAB_MEMBER_ROLE_NAME}' role")


def _create_user_preferences() -> None:
    """
    Create the table holding the per-user preferences document. The table
    may already exist on unversioned databases created from
    Base.metadata.create_all (replayed by the manual startup chain).
    """

    if sa.inspect(op.get_bind()).has_table("user_preferences"):
        return

    op.create_table(
        "user_preferences",
        sa.Column("user_id", models.GUID(), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.user_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )


def _add_user_quota_columns() -> None:
    """
    Add the per-user and per-group node quota columns. The columns may
    already exist on unversioned databases created from
    Base.metadata.create_all (replayed by the manual startup chain).
    """

    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    group_columns = {column["name"] for column in inspector.get_columns("user_groups")}

    for column in _USER_QUOTA_COLUMNS:
        if column not in user_columns:
            op.add_column("users", sa.Column(column, sa.Integer(), nullable=True))
    for column in _GROUP_QUOTA_COLUMNS:
        if column not in group_columns:
            op.add_column("user_groups", sa.Column(column, sa.Integer(), nullable=True))


def _create_distribution_records() -> None:
    """
    Create the table persisting the project distribution jobs and grant the
    "User" role to the "Users" group on the cross-project distribution
    listing, like the other default resource paths (the after_create
    seeding only runs on a new database). The insert is idempotent so it
    also re-seeds unversioned databases whose ACLs were wiped before the
    startup chain runs.
    """

    if not sa.inspect(op.get_bind()).has_table("distribution_records"):
        op.create_table(
            "distribution_records",
            sa.Column("distribution_id", models.GUID(), nullable=False),
            sa.Column("project_id", models.GUID(), nullable=False),
            sa.Column("name", sa.String(), nullable=True),
            sa.Column("created_by", sa.String(), nullable=False),
            sa.Column("total", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("cancel_requested", sa.Boolean(), nullable=False),
            sa.Column("results", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
            sa.PrimaryKeyConstraint("distribution_id"),
        )
        op.create_index("ix_distribution_records_project_id", "distribution_records", ["project_id"])

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO acl (ace_id, ace_type, path, propagate, allowed, role_id, group_id)"
            " SELECT :ace_id, 'group', :path, 1, 1,"
            " (SELECT role_id FROM roles WHERE name = 'User'),"
            " (SELECT user_group_id FROM user_groups WHERE name = 'Users')"
            " WHERE NOT EXISTS ("
            " SELECT 1 FROM acl WHERE path = :path"
            " AND group_id = (SELECT user_group_id FROM user_groups WHERE name = 'Users'))"
        ),
        {"ace_id": uuid.uuid4().hex, "path": DISTRIBUTIONS_PATH},
    )


def _drop_distribution_records() -> None:

    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM acl WHERE path = :path AND ace_type = 'group'"
            " AND group_id = (SELECT user_group_id FROM user_groups WHERE name = 'Users')"
        ),
        {"path": DISTRIBUTIONS_PATH},
    )
    op.drop_index("ix_distribution_records_project_id", table_name="distribution_records")
    op.drop_table("distribution_records")


def _create_mcp_tool_whitelist() -> None:
    """
    Create the table holding the per-group MCP tool whitelist. The table
    may already exist on unversioned databases created from
    Base.metadata.create_all (replayed by the manual startup chain).
    """

    if sa.inspect(op.get_bind()).has_table("mcp_tool_whitelist"):
        return

    op.create_table(
        "mcp_tool_whitelist",
        sa.Column("user_group_id", models.GUID(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.ForeignKeyConstraint(["user_group_id"], ["user_groups.user_group_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_group_id", "tool_name"),
    )


def upgrade() -> None:

    connection = op.get_bind()

    _seed_default_aces(connection)
    _restrict_default_projects_ace(connection)
    _add_privileges(connection, (NOTIFICATION_PRIVILEGE,), ("Administrator",))
    _create_user_preferences()
    _add_lab_member_role(connection)
    _add_user_quota_columns()
    _add_privileges(connection, SERVER_PRIVILEGES, ("Administrator",))
    _add_privileges(connection, MARKER_PRIVILEGES, MARKER_ROLE_NAMES)
    _add_privileges(connection, PROJECT_ACTION_PRIVILEGES, PROJECT_ACTION_ROLE_NAMES)
    _create_distribution_records()
    _create_mcp_tool_whitelist()


def downgrade() -> None:

    connection = op.get_bind()

    op.drop_table("mcp_tool_whitelist")
    _drop_distribution_records()
    _remove_privileges(connection, (name for name, _ in PROJECT_ACTION_PRIVILEGES))
    _remove_privileges(connection, (name for name, _ in MARKER_PRIVILEGES))
    _remove_privileges(connection, (name for name, _ in SERVER_PRIVILEGES))
    for column in _GROUP_QUOTA_COLUMNS:
        op.drop_column("user_groups", column)
    for column in _USER_QUOTA_COLUMNS:
        op.drop_column("users", column)
    _remove_lab_member_role(connection)
    op.drop_table("user_preferences")
    _remove_privileges(connection, (NOTIFICATION_PRIVILEGE[0],))
    _restore_default_projects_ace(connection)
    _remove_default_aces(connection)
