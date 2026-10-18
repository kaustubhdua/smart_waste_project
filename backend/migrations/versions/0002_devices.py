"""Add per-device credential registry."""
from alembic import op
import sqlalchemy as sa

revision = "0002_devices"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "devices",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("bin_id", sa.String(80), sa.ForeignKey("bins.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_devices_bin_id", "devices", ["bin_id"])

def downgrade():
    op.drop_index("ix_devices_bin_id", table_name="devices")
    op.drop_table("devices")
