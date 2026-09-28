"""Track image availability and persistent synchronization jobs.

Revision ID: d9e8a2b7c401
Revises: c7e4a9f1d2b6
"""
from alembic import op
import sqlalchemy as sa

revision = "d9e8a2b7c401"
down_revision = "c7e4a9f1d2b6"
branch_labels = None
depends_on = None


def upgrade():
    # Startup also uses this for unversioned databases previously created from
    # metadata, which may already contain some/all of these additive fields.
    inspector = sa.inspect(op.get_bind())
    existing = {column["name"] for column in inspector.get_columns("images")}
    for column in (
        sa.Column("availability", sa.String(), nullable=False, server_default="unknown"),
        sa.Column("file_fingerprint", sa.String()),
        sa.Column("last_seen_at", sa.DateTime()),
        sa.Column("last_verified_at", sa.DateTime()),
        sa.Column("last_error", sa.String()),
    ):
        if column.name not in existing:
            op.add_column("images", column)
    if inspector.has_table("image_sync_jobs"):
        return
    op.create_table(
        "image_sync_jobs",
        sa.Column("job_id", sa.String(), primary_key=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("force_checksum", sa.Boolean(), nullable=False),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.current_timestamp()),
    )


def downgrade():
    op.drop_table("image_sync_jobs")
    # Do not rebuild images: dropping the old table during a SQLite batch
    # rebuild would cascade-delete image_template_map entries with FK enabled.
    for name in ("last_error", "last_verified_at", "last_seen_at", "file_fingerprint", "availability"):
        op.drop_column("images", name)
