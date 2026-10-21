"""Add tags field to templates

Revision ID: 98083573d011
Revises: 9a5292aa4389
Create Date: 2026-02-23 18:23:59.857607

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "98083573d011"
down_revision = "9a5292aa4389"
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.add_column("templates", sa.Column("tags", sa.String()))


def downgrade() -> None:

    op.drop_column("templates", "tags")
