"""phase2h_field_tasks — Add field_tasks table for operational crew dispatch.

Revision ID: 034ee128bcde
Revises: 023ddb14a692
Create Date: 2026-09-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = '034ee128bcde'
down_revision: Union[str, Sequence[str], None] = '023ddb14a692'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Phase 2H field_tasks table (safe additive migration)."""
    op.create_table(
        'field_tasks',
        sa.Column('task_id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('city_id', sa.String(length=32), server_default='mumbai', nullable=True),
        sa.Column('task_type', sa.String(length=64), nullable=False),
        sa.Column('ward_id', sa.String(length=32), nullable=False),
        sa.Column('location', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, from_text='ST_GeomFromEWKT', name='geometry'), nullable=False),
        sa.Column('priority', sa.String(length=32), server_default='HIGH', nullable=True),
        sa.Column('status', sa.String(length=32), server_default='PENDING', nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('assigned_to', sa.String(length=128), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('evidence_photo_url', sa.Text(), nullable=True),
        sa.Column('citizen_report_id', sa.UUID(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=True),
        sa.ForeignKeyConstraint(['citizen_report_id'], ['citizen_reports.report_id']),
        sa.PrimaryKeyConstraint('task_id'),
    )
    op.create_index('idx_field_tasks_status', 'field_tasks', ['status'], unique=False)
    op.create_index('idx_field_tasks_ward', 'field_tasks', ['ward_id'], unique=False)


def downgrade() -> None:
    """Drop field_tasks table on downgrade."""
    op.drop_index('idx_field_tasks_ward', table_name='field_tasks')
    op.drop_index('idx_field_tasks_status', table_name='field_tasks')
    op.drop_table('field_tasks')
