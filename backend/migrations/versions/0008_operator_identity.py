"""Add managed operator identities, expiring sessions and audit events."""
from alembic import op
import sqlalchemy as sa

revision = '0008_operator_identity'
down_revision = '0007_one_open_job_per_bin'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'operator_users',
        sa.Column('id', sa.String(length=80), primary_key=True),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='operator'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('failed_login_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('username', name='uq_operator_users_username'),
    )
    op.create_index('ix_operator_users_username', 'operator_users', ['username'], unique=True)
    op.create_table(
        'operator_sessions',
        sa.Column('id', sa.String(length=80), primary_key=True),
        sa.Column('operator_user_id', sa.String(length=80), sa.ForeignKey('operator_users.id'), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('token_hash', name='uq_operator_sessions_token_hash'),
    )
    op.create_index('ix_operator_sessions_operator_user_id', 'operator_sessions', ['operator_user_id'])
    op.create_index('ix_operator_sessions_expires_at', 'operator_sessions', ['expires_at'])
    op.create_table(
        'operator_bootstrap',
        sa.Column('id', sa.String(length=40), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        'operator_audit_events',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('actor_user_id', sa.String(length=80), sa.ForeignKey('operator_users.id'), nullable=True),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('subject', sa.String(length=128), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_operator_audit_events_actor_user_id', 'operator_audit_events', ['actor_user_id'])
    op.create_index('ix_operator_audit_events_action', 'operator_audit_events', ['action'])
    op.create_index('ix_operator_audit_events_created_at', 'operator_audit_events', ['created_at'])


def downgrade():
    op.drop_table('operator_bootstrap')
    op.drop_index('ix_operator_audit_events_created_at', table_name='operator_audit_events')
    op.drop_index('ix_operator_audit_events_action', table_name='operator_audit_events')
    op.drop_index('ix_operator_audit_events_actor_user_id', table_name='operator_audit_events')
    op.drop_table('operator_audit_events')
    op.drop_index('ix_operator_sessions_expires_at', table_name='operator_sessions')
    op.drop_index('ix_operator_sessions_operator_user_id', table_name='operator_sessions')
    op.drop_table('operator_sessions')
    op.drop_index('ix_operator_users_username', table_name='operator_users')
    op.drop_table('operator_users')
