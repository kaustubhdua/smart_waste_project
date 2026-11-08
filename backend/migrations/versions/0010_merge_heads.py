"""Merge the PostGIS geography index and driver-action idempotency branches.

Both 0009 revisions branched from 0008_operator_identity and touch unrelated
objects, so this revision carries no schema change; it only joins the history
into a single head so `alembic upgrade head` succeeds.
"""

revision = "0010_merge_heads"
down_revision = ("0009_bin_geography_index", "0009_driver_action_idempotency")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
