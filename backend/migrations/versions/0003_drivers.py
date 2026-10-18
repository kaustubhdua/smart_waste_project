"""Add scoped driver credentials."""
from alembic import op
import sqlalchemy as sa

revision = "0003_drivers"
down_revision = "0002_devices"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "drivers",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("vehicle_id", sa.String(80), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_drivers_vehicle_id", "drivers", ["vehicle_id"])

def downgrade():
    op.drop_index("ix_drivers_vehicle_id", table_name="drivers")
    op.drop_table("drivers")
