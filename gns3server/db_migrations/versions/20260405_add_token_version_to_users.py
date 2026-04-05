"""add token_version to users

Revision ID: 20260405_add_token_version_to_users
Revises: 20260303_create_llm_model_configs
Create Date: 2026-04-05

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20260405_add_token_version_to_users'
down_revision = 'ec4b7b198555'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = inspect(conn)
    columns = [col['name'] for col in inspector.get_columns('users')]
    if 'token_version' not in columns:
        op.add_column('users', sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('users', 'token_version')
