"""add netmiko_device_type to templates table

Revision ID: b3c7e2a91d4f
Revises: 8f2a1c4e9d3b
Create Date: 2026-08-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b3c7e2a91d4f'
down_revision = '8f2a1c4e9d3b'
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.add_column('templates', sa.Column('netmiko_device_type', sa.String()))


def downgrade() -> None:

    op.drop_column('templates', 'netmiko_device_type')
