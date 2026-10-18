"""Create initial smart waste platform schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("bins",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("capacity_liters", sa.Float(), nullable=False),
        sa.Column("criticality", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("source", sa.String(20), nullable=False, server_default="demo"),
        sa.Column("last_emptied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("vehicles",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("capacity_liters", sa.Float(), nullable=False),
        sa.Column("depot_latitude", sa.Float(), nullable=False),
        sa.Column("depot_longitude", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("telemetry",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("bin_id", sa.String(80), sa.ForeignKey("bins.id"), nullable=False),
        sa.Column("device_id", sa.String(100), nullable=False),
        sa.Column("message_id", sa.String(150), nullable=False),
        sa.Column("fill_percent", sa.Float(), nullable=False),
        sa.Column("measured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="live"),
        sa.UniqueConstraint("device_id", "message_id", name="uq_device_message"))
    op.create_index("ix_telemetry_bin_id", "telemetry", ["bin_id"])
    op.create_index("ix_telemetry_device_id", "telemetry", ["device_id"])
    op.create_index("ix_telemetry_measured_at", "telemetry", ["measured_at"])
    op.create_table("collection_jobs",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("bin_id", sa.String(80), sa.ForeignKey("bins.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="detected"),
        sa.Column("demand_liters", sa.Float(), nullable=False),
        sa.Column("priority", sa.Float(), nullable=False, server_default="0"),
        sa.Column("assigned_vehicle_id", sa.String(80), sa.ForeignKey("vehicles.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_collection_jobs_bin_id", "collection_jobs", ["bin_id"])
    op.create_index("ix_collection_jobs_status", "collection_jobs", ["status"])
    op.create_table("service_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(80), sa.ForeignKey("collection_jobs.id"), nullable=False),
        sa.Column("actor", sa.String(100), nullable=False),
        sa.Column("previous_status", sa.String(30), nullable=False),
        sa.Column("new_status", sa.String(30), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_service_events_job_id", "service_events", ["job_id"])
    op.create_table("route_plans",
        sa.Column("id", sa.String(80), primary_key=True),
        sa.Column("depot_latitude", sa.Float(), nullable=False),
        sa.Column("depot_longitude", sa.Float(), nullable=False),
        sa.Column("routing_provider", sa.String(40), nullable=False),
        sa.Column("solver", sa.String(120), nullable=False),
        sa.Column("total_distance_meters", sa.Float(), nullable=False),
        sa.Column("route_payload", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))

def downgrade():
    op.drop_table("route_plans")
    op.drop_index("ix_service_events_job_id", table_name="service_events")
    op.drop_table("service_events")
    op.drop_index("ix_collection_jobs_status", table_name="collection_jobs")
    op.drop_index("ix_collection_jobs_bin_id", table_name="collection_jobs")
    op.drop_table("collection_jobs")
    op.drop_index("ix_telemetry_measured_at", table_name="telemetry")
    op.drop_index("ix_telemetry_device_id", table_name="telemetry")
    op.drop_index("ix_telemetry_bin_id", table_name="telemetry")
    op.drop_table("telemetry")
    op.drop_table("vehicles")
    op.drop_table("bins")
