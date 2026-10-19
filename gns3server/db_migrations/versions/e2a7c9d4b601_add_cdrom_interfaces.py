"""Add QEMU CD/DVD interfaces."""

import sqlalchemy as sa
from alembic import op

revision = "e2a7c9d4b601"
down_revision = "a6c8e1b2d490"
branch_labels = None
depends_on = None


def upgrade():
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("qemu_templates")}
    for name in ("cdrom_interface", "cdrom2_interface"):
        if name in existing:
            continue
        op.add_column("qemu_templates", sa.Column(name, sa.String(), nullable=False, server_default="ide"))


def downgrade():
    op.drop_column("qemu_templates", "cdrom2_interface")
    op.drop_column("qemu_templates", "cdrom_interface")
