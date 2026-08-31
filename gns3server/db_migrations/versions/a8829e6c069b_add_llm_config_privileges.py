"""add llm config privileges to existing database

Revision ID: a8829e6c069b
Revises: aff810fc119a
Create Date: 2026-05-26

"""
from alembic import op
import sqlalchemy as sa
from uuid import uuid4

# revision identifiers, used by Alembic.
revision = 'a8829e6c069b'
down_revision = 'aff810fc119a'
branch_labels = None
depends_on = None

privileges_table = sa.table(
    'privileges',
    sa.column('privilege_id', sa.String),
    sa.column('name', sa.String),
    sa.column('description', sa.String),
)

roles_table = sa.table(
    'roles',
    sa.column('role_id', sa.String),
    sa.column('name', sa.String),
)

privilege_role_map = sa.table(
    'privilege_role_map',
    sa.column('privilege_id', sa.String),
    sa.column('role_id', sa.String),
)


def upgrade() -> None:
    conn = op.get_bind()

    # Insert new LLMConfig privileges if they don't already exist
    new_privileges = [
        {"name": "LLMConfig.Allocate", "description": "Create or delete an LLM model configuration"},
        {"name": "LLMConfig.Audit", "description": "View an LLM model configuration"},
        {"name": "LLMConfig.Modify", "description": "Update an LLM model configuration"},
    ]

    privilege_ids = {}
    for priv in new_privileges:
        result = conn.execute(
            sa.select(privileges_table.c.privilege_id).where(
                privileges_table.c.name == priv["name"]
            )
        ).fetchone()

        if result:
            privilege_ids[priv["name"]] = result[0]
        else:
            priv_id = str(uuid4())
            conn.execute(
                privileges_table.insert().values(
                    privilege_id=priv_id,
                    name=priv["name"],
                    description=priv["description"],
                )
            )
            privilege_ids[priv["name"]] = priv_id

    # Add LLMConfig.Audit and LLMConfig.Modify to the User role
    user_role = conn.execute(
        sa.select(roles_table.c.role_id).where(roles_table.c.name == "User")
    ).fetchone()

    if user_role:
        user_role_id = user_role[0]
        for priv_name in ("LLMConfig.Audit", "LLMConfig.Modify"):
            conn.execute(
                privilege_role_map.insert().values(
                    privilege_id=privilege_ids[priv_name],
                    role_id=user_role_id,
                )
            )


def downgrade() -> None:
    conn = op.get_bind()

    user_role = conn.execute(
        sa.select(roles_table.c.role_id).where(roles_table.c.name == "User")
    ).fetchone()

    if user_role:
        user_role_id = user_role[0]
        for priv_name in ("LLMConfig.Audit", "LLMConfig.Modify"):
            priv = conn.execute(
                sa.select(privileges_table.c.privilege_id).where(
                    privileges_table.c.name == priv_name
                )
            ).fetchone()
            if priv:
                conn.execute(
                    privilege_role_map.delete().where(
                        privilege_role_map.c.privilege_id == priv[0],
                        privilege_role_map.c.role_id == user_role_id,
                    )
                )

    for priv_name in ("LLMConfig.Allocate", "LLMConfig.Audit", "LLMConfig.Modify"):
        conn.execute(
            privileges_table.delete().where(
                privileges_table.c.name == priv_name
            )
        )
