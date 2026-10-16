"""phase2a_enhance_models — Safe additive migration.

Add new columns to alerts and simulation_runs tables.
Create new validation_reports and nowcast_runs tables.
DO NOT drop any existing tables, columns, or indexes.

Revision ID: 023ddb14a692
Revises: 000_baseline
Create Date: 2026-09-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = '023ddb14a692'
down_revision: Union[str, Sequence[str], None] = '000_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Phase 2A schema enhancements (additive only)."""

    # ── 1. Create nowcast_runs table ──
    op.create_table('nowcast_runs',
        sa.Column('nowcast_id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('city_id', sa.String(length=32), nullable=True),
        sa.Column('run_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('weather_timestamp', sa.DateTime(timezone=True), nullable=True),
        sa.Column('mean_rainfall_mmh', sa.Float(), nullable=True),
        sa.Column('max_rainfall_mmh', sa.Float(), nullable=True),
        sa.Column('weather_points_count', sa.Integer(), nullable=True),
        sa.Column('weather_source', sa.String(length=128), nullable=True),
        sa.Column('max_depth_m', sa.Float(), nullable=True),
        sa.Column('mean_depth_m', sa.Float(), nullable=True),
        sa.Column('flooded_cells', sa.Integer(), nullable=True),
        sa.Column('flooded_area_km2', sa.Float(), nullable=True),
        sa.Column('duration_hours', sa.Float(), nullable=True),
        sa.Column('grid_size', sa.Integer(), nullable=True),
        sa.Column('catchment', sa.String(length=128), nullable=True),
        sa.Column('mass_balance_error', sa.Float(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('confidence_level', sa.String(length=32), nullable=True),
        sa.Column('confidence_factors', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('rainfall_providers_used', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('rainfall_providers_failed', postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column('rainfall_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('flood_geojson', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('depth_statistics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ward_risk_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['simulation_runs.run_id']),
        sa.PrimaryKeyConstraint('nowcast_id'),
    )
    op.create_index('idx_nowcast_created', 'nowcast_runs', ['created_at'], unique=False)
    op.create_index('idx_nowcast_status', 'nowcast_runs', ['status'], unique=False)

    # ── 2. Create validation_reports table ──
    op.create_table('validation_reports',
        sa.Column('report_id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('city_id', sa.String(length=32), nullable=True),
        sa.Column('event_id', sa.String(length=128), nullable=True),
        sa.Column('run_id', sa.UUID(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=True),
        sa.Column('iou', sa.Float(), nullable=True),
        sa.Column('csi', sa.Float(), nullable=True),
        sa.Column('pod', sa.Float(), nullable=True),
        sa.Column('far', sa.Float(), nullable=True),
        sa.Column('precision', sa.Float(), nullable=True),
        sa.Column('rmse_m', sa.Float(), nullable=True),
        sa.Column('mae_m', sa.Float(), nullable=True),
        sa.Column('mass_balance_error', sa.Float(), nullable=True),
        sa.Column('observed_flooded_cells', sa.Integer(), nullable=True),
        sa.Column('predicted_flooded_cells', sa.Integer(), nullable=True),
        sa.Column('true_positives', sa.Integer(), nullable=True),
        sa.Column('false_positives', sa.Integer(), nullable=True),
        sa.Column('false_negatives', sa.Integer(), nullable=True),
        sa.Column('true_negatives', sa.Integer(), nullable=True),
        sa.Column('confusion_geojson', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('report_data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['simulation_runs.run_id']),
        sa.PrimaryKeyConstraint('report_id'),
    )
    op.create_index('idx_valreport_created', 'validation_reports', ['created_at'], unique=False)
    op.create_index('idx_valreport_event', 'validation_reports', ['event_id'], unique=False)

    # ── 3. Add new columns to alerts ──
    op.add_column('alerts', sa.Column('ward_id', sa.String(length=32), nullable=True))
    op.add_column('alerts', sa.Column('status', sa.String(length=32), nullable=True))
    op.add_column('alerts', sa.Column('valid_from', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True))
    op.add_column('alerts', sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True))
    op.add_column('alerts', sa.Column('source', sa.String(length=64), nullable=True))
    op.add_column('alerts', sa.Column('affected_population', sa.Integer(), nullable=True))
    op.add_column('alerts', sa.Column('recommended_action', sa.Text(), nullable=True))
    op.add_column('alerts', sa.Column('escalation_level', sa.Integer(), nullable=True))
    op.add_column('alerts', sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('alerts', sa.Column('acknowledged_by', sa.String(length=255), nullable=True))
    op.add_column('alerts', sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('alerts', sa.Column('resolution_notes', sa.Text(), nullable=True))
    op.add_column('alerts', sa.Column('deduplication_key', sa.String(length=255), nullable=True))
    op.add_column('alerts', sa.Column('confidence_score', sa.Float(), nullable=True))
    op.create_index('idx_alert_dedup', 'alerts', ['deduplication_key'], unique=False)
    op.create_index('idx_alert_issued', 'alerts', ['issued_at'], unique=False)
    op.create_index('idx_alert_severity', 'alerts', ['severity'], unique=False)
    op.create_index('idx_alert_status', 'alerts', ['status'], unique=False)
    # Note: idx_alert_geom on affected_area skipped — GiST index already exists from initial schema

    # ── 4. Add new columns to simulation_runs ──
    op.add_column('simulation_runs', sa.Column('runtime_seconds', sa.Float(), nullable=True))
    op.add_column('simulation_runs', sa.Column('max_depth_m', sa.Float(), nullable=True))
    op.add_column('simulation_runs', sa.Column('mean_depth_m', sa.Float(), nullable=True))
    op.add_column('simulation_runs', sa.Column('flooded_area_km2', sa.Float(), nullable=True))
    op.add_column('simulation_runs', sa.Column('flooded_cells', sa.Integer(), nullable=True))
    op.add_column('simulation_runs', sa.Column('terrain_version', sa.String(length=128), nullable=True))
    op.add_column('simulation_runs', sa.Column('parameter_set', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('simulation_runs', sa.Column('confidence_score', sa.Float(), nullable=True))
    op.add_column('simulation_runs', sa.Column('confidence_factors', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('simulation_runs', sa.Column('validation_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('simulation_runs', sa.Column('flood_extent_geojson_uri', sa.Text(), nullable=True))
    op.add_column('simulation_runs', sa.Column('rainfall_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.create_index('idx_simrun_created', 'simulation_runs', ['created_at'], unique=False)
    op.create_index('idx_simrun_status', 'simulation_runs', ['status'], unique=False)

    # ── 5. Set defaults for existing rows ──
    op.execute("UPDATE alerts SET status = 'active' WHERE status IS NULL;")
    op.execute("UPDATE alerts SET source = 'manual' WHERE source IS NULL;")
    op.execute("UPDATE alerts SET escalation_level = 0 WHERE escalation_level IS NULL;")


def downgrade() -> None:
    """Remove Phase 2A additions (safe rollback)."""
    # Drop new indexes
    op.drop_index('idx_simrun_status', table_name='simulation_runs')
    op.drop_index('idx_simrun_created', table_name='simulation_runs')
    op.drop_index('idx_alert_status', table_name='alerts')
    op.drop_index('idx_alert_severity', table_name='alerts')
    op.drop_index('idx_alert_issued', table_name='alerts')
    op.drop_index('idx_alert_dedup', table_name='alerts')

    # Drop new simulation_runs columns
    for col in ['rainfall_summary', 'flood_extent_geojson_uri', 'validation_metadata',
                'confidence_factors', 'confidence_score', 'parameter_set', 'terrain_version',
                'flooded_cells', 'flooded_area_km2', 'mean_depth_m', 'max_depth_m', 'runtime_seconds']:
        op.drop_column('simulation_runs', col)

    # Drop new alerts columns
    for col in ['confidence_score', 'deduplication_key', 'resolution_notes', 'resolved_at',
                'acknowledged_by', 'acknowledged_at', 'escalation_level', 'recommended_action',
                'affected_population', 'source', 'valid_until', 'valid_from', 'status', 'ward_id']:
        op.drop_column('alerts', col)

    # Drop new tables
    op.drop_index('idx_valreport_event', table_name='validation_reports')
    op.drop_index('idx_valreport_created', table_name='validation_reports')
    op.drop_table('validation_reports')
    op.drop_index('idx_nowcast_status', table_name='nowcast_runs')
    op.drop_index('idx_nowcast_created', table_name='nowcast_runs')
    op.drop_table('nowcast_runs')
