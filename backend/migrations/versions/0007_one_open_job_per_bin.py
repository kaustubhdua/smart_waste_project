"""Prevent more than one unverified collection job per bin.

The API preflight check is retained for a useful conflict message. This
partial unique index is the concurrency-safe invariant for PostgreSQL and
SQLite. Existing duplicate open jobs must be resolved before this migration.
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_one_open_job_per_bin"
down_revision = "0006_telemetry_bin_time_idx"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    duplicate = bind.execute(
        sa.text(
            "SELECT bin_id FROM collection_jobs "
            "WHERE status <> 'verified' "
            "GROUP BY bin_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate:
        raise RuntimeError(
            "Cannot add one-open-job-per-bin constraint: "
            f"bin {duplicate[0]!r} has multiple unverified jobs. "
            "Resolve duplicate jobs and rerun the migration."
        )

    predicate = sa.text("status <> 'verified'")
    op.create_index(
        "uq_collection_jobs_one_open_per_bin",
        "collection_jobs",
        ["bin_id"],
        unique=True,
        sqlite_where=predicate,
        postgresql_where=predicate,
    )


def downgrade():
    op.drop_index(
        "uq_collection_jobs_one_open_per_bin",
        table_name="collection_jobs",
    )
