"""Add model_configs field to user_groups table

Revision ID: 20260303_add_model_configs_to_groups
Revises: 20260301_validate_model_configs
Create Date: 2026-03-03

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260303_add_model_configs_to_groups'
down_revision = '20260301_validate_model_configs'
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.add_column('user_groups', sa.Column('model_configs', sa.Text(), nullable=True))


def downgrade() -> None:

    op.drop_column('user_groups', 'model_configs')
