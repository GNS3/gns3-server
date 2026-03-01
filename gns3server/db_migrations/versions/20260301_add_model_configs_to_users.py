"""Add model_configs field to users table

Revision ID: 20260301_add_model_configs
Revises: 98083573d011
Create Date: 2026-03-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260301_add_model_configs'
down_revision = '98083573d011'
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.add_column('users', sa.Column('model_configs', sa.Text(), nullable=True))


def downgrade() -> None:

    op.drop_column('users', 'model_configs')
