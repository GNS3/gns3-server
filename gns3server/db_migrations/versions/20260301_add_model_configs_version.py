"""Add model_configs_version column to users table for optimistic locking

Revision ID: 20260301_add_model_configs_version
Revises: 20260301_add_model_configs
Create Date: 2026-03-01

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = '20260301_add_model_configs_version'
down_revision = '20260301_add_model_configs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Get the current connection
    conn = op.get_bind()
    inspector = inspect(conn)

    # Check if column already exists (idempotent for new databases)
    columns = [col['name'] for col in inspector.get_columns('users')]

    if 'model_configs_version' not in columns:
        op.add_column('users', sa.Column('model_configs_version', sa.Integer(), nullable=False, server_default='0'))
    else:
        # Column exists from Base.metadata.create_all, ensure it has the right defaults
        pass


def downgrade() -> None:
    op.drop_column('users', 'model_configs_version')
