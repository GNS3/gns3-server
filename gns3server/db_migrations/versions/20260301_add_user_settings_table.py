"""Add user settings table

Revision ID: 20260301_add_user_settings
Revises: 98083573d011
Create Date: 2026-03-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260301_add_user_settings'
down_revision = '98083573d011'
branch_labels = None
depends_on = None


def upgrade() -> None:

    op.create_table(
        'user_settings',
        sa.Column('setting_id', sa.String(32), primary_key=True),
        sa.Column('user_id', sa.String(32), sa.ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False),
        sa.Column('key', sa.String(255), nullable=False),
        sa.Column('value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP')),
        sa.UniqueConstraint('user_id', 'key', name='unique_user_setting')
    )


def downgrade() -> None:

    op.drop_table('user_settings')
