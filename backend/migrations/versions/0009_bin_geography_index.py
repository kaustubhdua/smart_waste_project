"""Add a functional PostGIS GiST index for bin proximity searches."""
from alembic import op

revision = "0009_bin_geography_index"
down_revision = "0008_operator_identity"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # The production Compose image is postgis/postgis. Enable the extension
        # before indexing coordinate-derived geography values.
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_bins_geography_gist "
            "ON bins USING GIST "
            "((ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography))"
        )


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_bins_geography_gist")
