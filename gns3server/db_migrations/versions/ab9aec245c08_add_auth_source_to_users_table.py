"""add auth_source to users table

Revision ID: ab9aec245c08
Revises: b7d4c3f2a1e9
Create Date: 2026-11-09 15:57:12.659920

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ab9aec245c08"
down_revision = "b7d4c3f2a1e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    if "auth_source" not in existing:
        op.add_column("users", sa.Column("auth_source", sa.String(), nullable=False, server_default="local"))
    if "external_id" not in existing:
        op.add_column("users", sa.Column("external_id", sa.String(), nullable=True))
        op.create_index("ix_users_external_id", "users", ["external_id"])
    if "ldap_groups" not in existing:
        op.add_column("users", sa.Column("ldap_groups", sa.String(), nullable=True))


def downgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}
    if "ldap_groups" in existing:
        op.drop_column("users", "ldap_groups")
    if "external_id" in existing:
        op.drop_index("ix_users_external_id", table_name="users")
        op.drop_column("users", "external_id")
    if "auth_source" in existing:
        op.drop_column("users", "auth_source")
