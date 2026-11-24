"""create event_log table

Revision ID: 0001_create_event_log_table
Revises:
Create Date: 2026-01-09 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_create_event_log_table'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'event_log',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('event_id', sa.String(36), nullable=False, unique=True, index=True),
        sa.Column('source_fragment_id', sa.String(100), nullable=False, index=True),
        sa.Column('event_type', sa.String(50), nullable=False, server_default='counter_update'),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('event_timestamp', sa.DateTime(), nullable=False),
        sa.Column('received_at', sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table('event_log')
