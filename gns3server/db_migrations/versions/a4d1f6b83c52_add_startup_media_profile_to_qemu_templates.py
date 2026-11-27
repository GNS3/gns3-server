"""Add startup_media_profile to QEMU templates."""

import sqlalchemy as sa
from alembic import op

revision = "a4d1f6b83c52"
down_revision = "ab9aec245c08"
branch_labels = None
depends_on = None


def upgrade():
    # Idempotent: databases touched by earlier builds may already have the column.
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("qemu_templates")}
    if "startup_media_profile" not in existing:
        op.add_column("qemu_templates", sa.Column("startup_media_profile", sa.String()))


def downgrade():
    op.drop_column("qemu_templates", "startup_media_profile")
