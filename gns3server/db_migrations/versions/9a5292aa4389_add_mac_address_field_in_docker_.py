"""add mac_address field in Docker templates table

Revision ID: 9a5292aa4389
Revises: 7ceeddd9c9a8
Create Date: 2024-09-18 17:52:53.429522

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a5292aa4389'
down_revision = '7ceeddd9c9a8'
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.add_column('docker_templates', sa.Column('mac_address', sa.String()))


def downgrade() -> None:

    op.drop_column('docker_templates', 'mac_address')

