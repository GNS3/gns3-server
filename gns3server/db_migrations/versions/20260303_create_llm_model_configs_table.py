"""create llm_model_configs table

Revision ID: 20260303_create_llm_model_configs
Revises: 98083573d011
Create Date: 2026-03-03

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = '20260303_create_llm_model_configs'
down_revision = '98083573d011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Get the current connection and dialect
    conn = op.get_bind()
    inspector = inspect(conn)
    dialect_name = conn.dialect.name

    # Check if table already exists (idempotent for databases created from code)
    tables = inspector.get_table_names()

    if 'llm_model_configs' in tables:
        # Table already exists from Base.metadata.create_all, skip creation
        return

    # Create llm_model_configs table with cross-database compatible types
    op.create_table(
        'llm_model_configs',
        sa.Column('config_id', sa.String(32), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('model_type', sa.String(50), nullable=False),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('user_id', sa.String(32), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=True),
        sa.Column('group_id', sa.String(32), sa.ForeignKey('user_groups.user_group_id', ondelete='CASCADE'), nullable=True),
        sa.Column('is_default', sa.Boolean(), default=False, nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "(user_id IS NOT NULL AND group_id IS NULL) OR "
            "(user_id IS NULL AND group_id IS NOT NULL)",
            name='single_owner_check'
        ),
        sa.CheckConstraint(
            "model_type IN ('text', 'vision', 'stt', 'tts', 'multimodal', 'embedding', 'reranking', 'other')",
            name='valid_model_type_check'
        ),
    )

    # Create indexes for efficient queries
    op.create_index('idx_llm_model_configs_user_id', 'llm_model_configs', ['user_id'])
    op.create_index('idx_llm_model_configs_group_id', 'llm_model_configs', ['group_id'])
    op.create_index('idx_llm_model_configs_model_type', 'llm_model_configs', ['model_type'])

    # PostgreSQL-specific indexes
    if dialect_name == 'postgresql':
        # GIN index for JSONB config column
        op.create_index('idx_llm_model_configs_config', 'llm_model_configs', ['config'], postgresql_using='gin')

        # Partial unique indexes for default configs
        op.execute("""
            CREATE UNIQUE INDEX unique_user_default
            ON llm_model_configs (user_id)
            WHERE is_default = TRUE AND user_id IS NOT NULL
        """)
        op.execute("""
            CREATE UNIQUE INDEX unique_group_default
            ON llm_model_configs (group_id)
            WHERE is_default = TRUE AND group_id IS NOT NULL
        """)


def downgrade() -> None:
    # Get the current connection and dialect
    conn = op.get_bind()
    dialect_name = conn.dialect.name

    # Drop indexes
    op.drop_index('idx_llm_model_configs_model_type', table_name='llm_model_configs')
    op.drop_index('idx_llm_model_configs_group_id', table_name='llm_model_configs')
    op.drop_index('idx_llm_model_configs_user_id', table_name='llm_model_configs')

    if dialect_name == 'postgresql':
        op.drop_index('idx_llm_model_configs_config', table_name='llm_model_configs')
        op.drop_index('unique_user_default', table_name='llm_model_configs')
        op.drop_index('unique_group_default', table_name='llm_model_configs')

    # Drop table
    op.drop_table('llm_model_configs')
