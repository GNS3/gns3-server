"""Add copilot config table

Revision ID: 20250227_add_copilot_config
Revises: 98083573d011
Create Date: 2025-02-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250227_add_copilot_config'
down_revision = '98083573d011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create copilot_configs table
    op.create_table(
        'copilot_configs',
        sa.Column('config_id', sa.String(32), primary_key=True),
        sa.Column('user_id', sa.String(32), sa.ForeignKey('users.user_id', ondelete='CASCADE'), unique=True, index=True),
        sa.Column('provider', sa.String(), default='openai'),
        sa.Column('model_name', sa.String(), default='gpt-4o'),
        sa.Column('api_key', sa.String()),
        sa.Column('base_url', sa.String(), nullable=True),
        sa.Column('temperature', sa.Float(), default=0.7),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('enabled', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), onupdate=sa.func.current_timestamp()),
    )


def downgrade() -> None:
    op.drop_table('copilot_configs')
