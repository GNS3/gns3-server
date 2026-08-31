"""add api_keys table

Revision ID: f0b0de2a9
Revises: a8829e6c069b
Create Date: 2026-06-11 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import gns3server.db.models.base as models

# revision identifiers, used by Alembic.
revision = 'f0b0de2a9'
down_revision = 'a8829e6c069b'
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.create_table(
        'api_keys',
        sa.Column('api_key_id', models.GUID(), nullable=False),
        sa.Column('user_id', models.GUID(), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('key_hash', sa.String(128), nullable=False),
        sa.Column('key_prefix', sa.String(8), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.current_timestamp(), nullable=False),
        sa.Column('revoked', sa.Boolean(), default=False, nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.user_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('api_key_id'),
    )
    op.create_index('ix_api_keys_user_id', 'api_keys', ['user_id'])
    op.create_index('ix_api_keys_key_hash', 'api_keys', ['key_hash'])


def downgrade() -> None:

    op.drop_index('ix_api_keys_key_hash', table_name='api_keys')
    op.drop_index('ix_api_keys_user_id', table_name='api_keys')
    op.drop_table('api_keys')
