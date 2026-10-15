"""add auto_connect to computes table

Revision ID: f7d3a9c2e5b1
Revises: d9e8a2b7c401
Create Date: 2026-10-15 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "f7d3a9c2e5b1"
down_revision = "d9e8a2b7c401"
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.add_column("computes", sa.Column("auto_connect", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:

    op.drop_column("computes", "auto_connect")
