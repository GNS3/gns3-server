"""add extra_configs to docker templates table

Revision ID: 8f2a1c4e9d3b
Revises: f0b0de2a9
Create Date: 2026-08-14 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8f2a1c4e9d3b'
down_revision = 'f0b0de2a9'
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.add_column('docker_templates', sa.Column('extra_configs', sa.JSON()))


def downgrade() -> None:

    op.drop_column('docker_templates', 'extra_configs')
