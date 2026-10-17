"""Add a second QEMU CD-ROM image.

Revision ID: a6c8e1b2d490
Revises: f7d3a9c2e5b1
"""

import sqlalchemy as sa
from alembic import op

revision = "a6c8e1b2d490"
down_revision = "f7d3a9c2e5b1"
branch_labels = None
depends_on = None


def upgrade():
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("qemu_templates")}
    if "cdrom2_image" not in existing:
        op.add_column("qemu_templates", sa.Column("cdrom2_image", sa.String()))


def downgrade():
    op.drop_column("qemu_templates", "cdrom2_image")
