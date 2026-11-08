"""Restrict the default /projects ACE to the project collection.

The default ACE granting the "User" role to the "Users" group on /projects
used to propagate to every project path, so every user could access every
project by ID. Projects are now private to their creator until they are
shared through an explicit ACE or a resource pool: the default ACE keeps
only the collection endpoints (POST /projects), while a per-project owner
ACE is created when a project is created.

Only the exact seeded ACE is updated: an ACE an administrator customized
(different role, group, allowed flag or propagate flag) is left untouched.

Revision ID: b5f3a8c1d902
Revises: c5e9a3f7d821
"""

import logging

import sqlalchemy as sa
from alembic import op

revision = "b5f3a8c1d902"
down_revision = "c5e9a3f7d821"
branch_labels = None
depends_on = None

log = logging.getLogger(__name__)

# Keep in sync with create_default_aces in gns3server/db/models/acl.py
_UPDATE_SEEDED_ACE = sa.text(
    "UPDATE acl SET propagate = :new_value"
    " WHERE path = '/projects' AND user_id IS NULL AND allowed = 1 AND propagate = :old_value"
    " AND group_id = (SELECT user_group_id FROM user_groups WHERE name = 'Users')"
    " AND role_id = (SELECT role_id FROM roles WHERE name = 'User')"
)


def upgrade():
    """
    Stop the seeded /projects ACE from propagating to the projects.
    """

    connection = op.get_bind()
    result = connection.execute(_UPDATE_SEEDED_ACE, {"new_value": 0, "old_value": 1})
    log.info(f"Restricted {result.rowcount} default /projects ACE(s) to the project collection")


def downgrade():
    """
    Restore the old propagating default ACE.
    """

    connection = op.get_bind()
    result = connection.execute(_UPDATE_SEEDED_ACE, {"new_value": 1, "old_value": 0})
    log.info(f"Restored {result.rowcount} default /projects ACE(s) to the propagating shape")
