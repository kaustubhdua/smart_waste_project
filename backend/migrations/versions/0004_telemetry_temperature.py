"""Add optional temperature measurement for model features."""
from alembic import op
import sqlalchemy as sa

revision = "0004_temperature"
down_revision = "0003_drivers"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("telemetry", sa.Column("temperature_c", sa.Float(), nullable=True))

def downgrade():
    op.drop_column("telemetry", "temperature_c")
