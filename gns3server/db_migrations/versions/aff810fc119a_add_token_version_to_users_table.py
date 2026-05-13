"""add token version to users table

Revision ID: aff810fc119a
Revises: ec4b7b198555
Create Date: 2026-04-06 19:49:12.155446

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'aff810fc119a'
down_revision = 'ec4b7b198555'
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.add_column('users', sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'))

def downgrade() -> None:

    op.drop_column('users', 'token_version')
