"""Track vehicle route availability to prevent conflicting dispatches."""
from alembic import op
import sqlalchemy as sa

revision = "0005_vehicle_availability"
down_revision = "0004_temperature"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("vehicles", sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.true()))

def downgrade():
    op.drop_column("vehicles", "available")
