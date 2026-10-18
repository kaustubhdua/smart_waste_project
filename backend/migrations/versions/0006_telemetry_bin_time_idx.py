"""Index latest telemetry lookups by bin and observation time."""
from alembic import op

revision = "0006_telemetry_bin_time_idx"
down_revision = "0005_vehicle_availability"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_telemetry_bin_measured_at",
        "telemetry",
        ["bin_id", "measured_at"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_telemetry_bin_measured_at", table_name="telemetry")
