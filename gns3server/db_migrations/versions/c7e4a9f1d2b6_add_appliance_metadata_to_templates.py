"""add appliance_metadata to templates table

Revision ID: c7e4a9f1d2b6
Revises: b3c7e2a91d4f
Create Date: 2026-08-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7e4a9f1d2b6'
down_revision = 'b3c7e2a91d4f'
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.add_column('templates', sa.Column('appliance_metadata', sa.JSON()))


def downgrade() -> None:

    op.drop_column('templates', 'appliance_metadata')
