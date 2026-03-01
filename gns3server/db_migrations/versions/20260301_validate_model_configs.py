"""Validate and fix existing model_configs JSON data

Revision ID: 20260301_validate_model_configs
Revises: 20260301_add_model_configs_version
Create Date: 2026-03-01

"""
import json
import logging
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


log = logging.getLogger(__name__)

# revision identifiers, used by Alembic.
revision = '20260301_validate_model_configs'
down_revision = '20260301_add_model_configs_version'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Validate all existing model_configs JSON data.
    Fix invalid JSON by setting to default value.
    """

    # Get database connection
    conn = op.get_bind()

    # Create a table reference for updates
    users_table = table('users',
        column('user_id', sa.String),
        column('model_configs', sa.Text),
        column('model_configs_version', sa.Integer)
    )

    # Fetch all users with model_configs
    result = conn.execute(sa.text(
        "SELECT user_id, model_configs FROM users WHERE model_configs IS NOT NULL"
    ))

    fixed_count = 0
    total_count = 0

    for row in result:
        user_id, model_configs = row
        total_count += 1

        if not model_configs or not model_configs.strip():
            # Empty string, set to NULL
            conn.execute(
                users_table.update()
                .where(users_table.c.user_id == user_id)
                .values(model_configs=None)
            )
            fixed_count += 1
            log.info(f"User {user_id}: Empty model_configs set to NULL")
            continue

        try:
            # Try to parse JSON
            config_data = json.loads(model_configs)

            # Validate structure
            if not isinstance(config_data, dict):
                raise ValueError("model_configs is not a dict")

            # Ensure required fields exist
            if 'profiles' not in config_data:
                config_data['profiles'] = []
                log.warning(f"User {user_id}: Missing 'profiles' field, added empty list")

            if 'active' not in config_data:
                if config_data['profiles']:
                    config_data['active'] = config_data['profiles'][0].get('name', 'default')
                else:
                    config_data['active'] = 'default'
                log.warning(f"User {user_id}: Missing 'active' field, set to '{config_data['active']}'")

            # Update with validated data
            conn.execute(
                users_table.update()
                .where(users_table.c.user_id == user_id)
                .values(model_configs=json.dumps(config_data))
            )

        except (json.JSONDecodeError, ValueError) as e:
            # Invalid JSON, set to default
            default_config = json.dumps({"profiles": [], "active": "default"})
            conn.execute(
                users_table.update()
                .where(users_table.c.user_id == user_id)
                .values(model_configs=default_config)
            )
            fixed_count += 1
            log.warning(f"User {user_id}: Invalid model_configs JSON ({e}), reset to default")

    log.info(f"Validated {total_count} model_configs, fixed {fixed_count} invalid entries")


def downgrade() -> None:
    """
    No-op for downgrade.
    We don't want to re-introduce invalid JSON data.
    """
    pass
