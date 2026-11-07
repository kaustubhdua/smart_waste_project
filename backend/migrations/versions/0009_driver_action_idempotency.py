"""Persist idempotency keys for driver collection actions."""
from alembic import op
import sqlalchemy as sa

revision = '0009_driver_action_idempotency'
down_revision = '0008_operator_identity'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'driver_actions',
        sa.Column('idempotency_key', sa.String(length=128), primary_key=True),
        sa.Column('driver_id', sa.String(length=100), sa.ForeignKey('drivers.id'), nullable=False),
        sa.Column('job_id', sa.String(length=80), sa.ForeignKey('collection_jobs.id'), nullable=False),
        sa.Column('action', sa.String(length=30), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('response_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_driver_actions_driver_id', 'driver_actions', ['driver_id'])
    op.create_index('ix_driver_actions_job_id', 'driver_actions', ['job_id'])


def downgrade():
    op.drop_index('ix_driver_actions_job_id', table_name='driver_actions')
    op.drop_index('ix_driver_actions_driver_id', table_name='driver_actions')
    op.drop_table('driver_actions')
