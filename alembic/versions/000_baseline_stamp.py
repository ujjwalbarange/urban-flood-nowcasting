"""000_baseline_stamp — Mark existing schema as migration baseline.

All 17 ORM-mapped tables already exist in the production PostGIS database.
This migration is an intentional no-op that establishes the alembic_version
tracking without attempting to create or drop any existing tables.

Existing tables (verified 2026-09-26):
  cities, wards, dem_tiles, drainage_nodes, drainage_links,
  road_segments, rainfall_observations, simulation_runs, flood_snapshots,
  citizen_reports, shelters, alerts, historical_flood_events,
  pumping_stations, critical_infrastructure, data_sources, flood_hotspots

Plus 27 additional data-only tables not managed by ORM.

Revision ID: 000_baseline
Revises: (none)
Create Date: 2026-09-26
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "000_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Baseline stamp — no schema changes.

    All tables already exist in the production database.
    This migration simply establishes alembic_version tracking.
    """
    pass


def downgrade() -> None:
    """Downgrade is a no-op for the baseline.

    We cannot drop existing production tables that predate Alembic.
    """
    pass
