"""SQLAlchemy ORM models for PostGIS-backed tables."""

from __future__ import annotations

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import relationship

from services.database.connection import Base


class City(Base):
    """City configuration table."""

    __tablename__ = "cities"

    city_id = Column(String(32), primary_key=True)
    name = Column(String(255), nullable=False)
    state = Column(String(128), default="")
    country = Column(String(4), default="IN")
    crs_epsg = Column(Integer, nullable=False)
    cell_size_m = Column(Float, default=30.0)
    bbox = Column(Geometry("POLYGON", srid=4326))
    timezone = Column(String(64), default="Asia/Kolkata")
    config = Column(JSONB, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    wards = relationship("Ward", back_populates="city", lazy="selectin")


class Ward(Base):
    """Administrative ward boundaries."""

    __tablename__ = "wards"

    ward_id = Column(String(32), primary_key=True)
    city_id = Column(String(32), ForeignKey("cities.city_id"), nullable=False)
    name = Column(String(255))
    geometry = Column(Geometry("MULTIPOLYGON", srid=4326), nullable=False)
    area_sq_km = Column(Float)
    population = Column(Integer)
    metadata_ = Column("metadata", JSONB, default={})

    city = relationship("City", back_populates="wards")

    __table_args__ = (
        Index("idx_wards_geom", geometry, postgresql_using="gist"),
    )


class DEMTile(Base):
    """DEM raster tile metadata (actual rasters in object storage)."""

    __tablename__ = "dem_tiles"

    tile_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    city_id = Column(String(32), ForeignKey("cities.city_id"))
    source = Column(String(128))
    crs_epsg = Column(Integer, nullable=False)
    resolution_m = Column(Float, nullable=False)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    bounds = Column(Geometry("POLYGON", srid=4326))
    storage_uri = Column(Text, nullable=False)
    sha256 = Column(String(64))
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())
    provenance = Column(JSONB, default={})


class DrainageNodeDB(Base):
    """Drainage network node (manhole/inlet/outfall/junction)."""

    __tablename__ = "drainage_nodes"

    node_id = Column(String(64), primary_key=True)
    city_id = Column(String(32), ForeignKey("cities.city_id"))
    node_type = Column(String(32))
    geometry = Column(Geometry("POINT", srid=4326), nullable=False)
    invert_elevation_m = Column(Float)
    ground_elevation_m = Column(Float)
    data_quality = Column(String(32), default="assumed")
    attributes = Column(JSONB, default={})

    __table_args__ = (
        Index("idx_drain_nodes_geom", geometry, postgresql_using="gist"),
    )


class DrainageLinkDB(Base):
    """Drainage network link (pipe/channel/culvert)."""

    __tablename__ = "drainage_links"

    link_id = Column(String(64), primary_key=True)
    city_id = Column(String(32), ForeignKey("cities.city_id"))
    from_node = Column(String(64), ForeignKey("drainage_nodes.node_id"))
    to_node = Column(String(64), ForeignKey("drainage_nodes.node_id"))
    link_type = Column(String(32))
    geometry = Column(Geometry("LINESTRING", srid=4326))
    diameter_m = Column(Float)
    length_m = Column(Float)
    manning_n = Column(Float)
    data_quality = Column(String(32), default="assumed")
    attributes = Column(JSONB, default={})


class RoadSegment(Base):
    """Road network segment."""

    __tablename__ = "road_segments"

    segment_id = Column(String(64), primary_key=True)
    city_id = Column(String(32), ForeignKey("cities.city_id"))
    name = Column(String(255))
    road_class = Column(String(64))
    geometry = Column(Geometry("LINESTRING", srid=4326), nullable=False)
    length_m = Column(Float)
    speed_limit_kmh = Column(Float)
    osm_id = Column(BigInteger)
    attributes = Column(JSONB, default={})

    __table_args__ = (
        Index("idx_roads_geom", geometry, postgresql_using="gist"),
    )


class RainfallObservationDB(Base):
    """Rainfall observation record."""

    __tablename__ = "rainfall_observations"

    obs_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    city_id = Column(String(32))
    source = Column(String(64))
    observed_at = Column(DateTime(timezone=True), nullable=False)
    valid_from = Column(DateTime(timezone=True))
    valid_to = Column(DateTime(timezone=True))
    rate_mmh = Column(Float)
    spatial_type = Column(String(32))
    location = Column(Geometry("POINT", srid=4326))
    grid_storage_uri = Column(Text)
    quality_flags = Column(ARRAY(Text))
    provenance = Column(JSONB, default={})

    __table_args__ = (
        Index("idx_rainfall_time", observed_at),
        Index("idx_rainfall_city", city_id, observed_at),
    )


class SimulationRun(Base):
    """Simulation run record."""

    __tablename__ = "simulation_runs"

    run_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    city_id = Column(String(32), ForeignKey("cities.city_id"))
    mode = Column(String(32), nullable=False)
    status = Column(String(32), default="queued")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    scenario_config = Column(JSONB, nullable=False)
    mass_balance = Column(JSONB)
    output_manifest = Column(JSONB)
    error = Column(JSONB)


class FloodSnapshotDB(Base):
    """Flood depth snapshot at a simulation time step."""

    __tablename__ = "flood_snapshots"

    snapshot_id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    run_id = Column(UUID(as_uuid=True), ForeignKey("simulation_runs.run_id"))
    valid_time = Column(DateTime(timezone=True), nullable=False)
    lead_minutes = Column(Integer)
    max_depth_m = Column(Float)
    mean_depth_m = Column(Float)
    flooded_cells = Column(Integer)
    flooded_area_m2 = Column(Float)
    extent_threshold_m = Column(Float, default=0.05)
    depth_grid_uri = Column(Text)
    statistics = Column(JSONB, default={})


class CitizenReport(Base):
    """Citizen flood/incident report."""

    __tablename__ = "citizen_reports"

    report_id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    city_id = Column(String(32))
    reporter_name = Column(String(255))
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    ward_id = Column(String(32))
    reported_at = Column(DateTime(timezone=True), server_default=func.now())
    water_depth_cm = Column(Float)
    description = Column(Text)
    photo_url = Column(Text)
    report_type = Column(String(32))
    verification_status = Column(String(32), default="unverified")
    metadata_ = Column("metadata", JSONB, default={})

    __table_args__ = (
        Index("idx_reports_geom", location, postgresql_using="gist"),
        Index("idx_reports_time", reported_at),
    )


class Shelter(Base):
    """Emergency shelter / relief center."""

    __tablename__ = "shelters"

    shelter_id = Column(String(64), primary_key=True)
    city_id = Column(String(32), ForeignKey("cities.city_id"))
    name = Column(String(255), nullable=False)
    category = Column(String(64))
    capacity_persons = Column(Integer)
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    elevation_m = Column(Float)
    status = Column(String(32), default="operational")
    attributes = Column(JSONB, default={})


class Alert(Base):
    """Flood alert / warning."""

    __tablename__ = "alerts"

    alert_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    city_id = Column(String(32))
    run_id = Column(UUID(as_uuid=True), ForeignKey("simulation_runs.run_id"))
    severity = Column(String(32))
    cap_xml = Column(Text)
    issued_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))
    affected_area = Column(Geometry("POLYGON", srid=4326))
    affected_wards = Column(ARRAY(Text))
    metadata_ = Column("metadata", JSONB, default={})


class HistoricalFloodEvent(Base):
    """Historical flood event observation — real observed data point."""

    __tablename__ = "historical_flood_events"

    event_id = Column(String(64), primary_key=True)
    city_id = Column(String(32), default="mumbai")
    date = Column(DateTime(timezone=True), nullable=False)
    year = Column(Integer)
    ward = Column(String(128))
    locality = Column(Text)
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    elevation_m = Column(Float)
    slope_degree = Column(Float)
    distance_to_drain_m = Column(Float)
    distance_to_waterbody_m = Column(Float)

    # Rainfall metrics
    rainfall_1h_mm = Column(Float)
    rainfall_3h_mm = Column(Float)
    rainfall_6h_mm = Column(Float)
    rainfall_12h_mm = Column(Float)
    rainfall_24h_mm = Column(Float)
    rainfall_48h_mm = Column(Float)
    rainfall_72h_mm = Column(Float)
    rainfall_intensity_mm_h = Column(Float)
    rainfall_anomaly = Column(Float)
    antecedent_rainfall_3day_mm = Column(Float)
    antecedent_rainfall_7day_mm = Column(Float)

    # Land/soil
    soil_moisture = Column(Float)
    soil_type = Column(String(128))
    infiltration_rate = Column(Float)
    groundwater_level_m = Column(Float)
    drain_water_level_m = Column(Float)
    built_up_percentage = Column(Float)
    impervious_surface_percentage = Column(Float)
    vegetation_percentage = Column(Float)
    population_density = Column(Float)
    drainage_capacity = Column(Float)

    # Remote sensing indices
    ndvi = Column(Float)
    ndwi = Column(Float)
    ndbi = Column(Float)

    # Flood impact
    flooded_area_km2 = Column(Float)
    flood_occurred = Column(Boolean, default=True)
    flood_depth_cm = Column(Float)
    flood_duration_hours = Column(Float)
    waterlogging_duration_hours = Column(Float)
    flood_severity = Column(String(32))
    people_affected = Column(Integer)
    houses_affected = Column(Integer)
    roads_affected = Column(Integer)
    economic_loss = Column(Float)

    # Derived indices
    rainfall_intensity_index = Column(Float)
    drainage_stress_index = Column(Float)
    imperviousness_index = Column(Float)

    # Provenance
    data_source = Column(Text)
    source_url = Column(Text)
    data_type = Column(String(32))  # observed / satellite_derived / modelled
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_hist_flood_geom", location, postgresql_using="gist"),
        Index("idx_hist_flood_date", date),
        Index("idx_hist_flood_ward", ward),
    )


class PumpingStation(Base):
    """Municipal pumping station."""

    __tablename__ = "pumping_stations"

    pump_id = Column(String(64), primary_key=True)
    city_id = Column(String(32), ForeignKey("cities.city_id"))
    name = Column(String(255), nullable=False)
    ward = Column(String(128))
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    num_pumps = Column(Integer)
    rated_capacity_mld = Column(Float)
    current_status = Column(String(32), default="operational")
    operational_capacity_pct = Column(Float, default=100.0)
    data_source = Column(Text)
    last_updated = Column(DateTime(timezone=True), server_default=func.now())
    attributes = Column(JSONB, default={})


class CriticalInfrastructure(Base):
    """Critical infrastructure (hospitals, schools, fire stations, etc.)."""

    __tablename__ = "critical_infrastructure"

    infra_id = Column(String(64), primary_key=True)
    city_id = Column(String(32), default="mumbai")
    name = Column(String(255), nullable=False)
    category = Column(String(64))  # hospital, school, fire_station, police, railway, metro
    ward = Column(String(128))
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    capacity = Column(Integer)
    elevation_m = Column(Float)
    flood_vulnerable = Column(Boolean, default=False)
    data_source = Column(Text)
    attributes = Column(JSONB, default={})

    __table_args__ = (
        Index("idx_infra_geom", location, postgresql_using="gist"),
    )


class DataSource(Base):
    """Registry of data sources / providers for provenance tracking."""

    __tablename__ = "data_sources"

    source_id = Column(String(64), primary_key=True)
    provider_name = Column(String(255), nullable=False)
    provider_type = Column(String(64))  # api, file, satellite, gauge, derived
    description = Column(Text)
    url = Column(Text)
    license = Column(String(255))
    spatial_resolution = Column(String(64))
    temporal_resolution = Column(String(64))
    crs = Column(String(32), default="EPSG:4326")
    status = Column(String(32), default="available")
    last_successful_fetch = Column(DateTime(timezone=True))
    error_message = Column(Text)
    config = Column(JSONB, default={})


class FloodHotspot(Base):
    """Known chronic flood-prone location."""

    __tablename__ = "flood_hotspots"

    hotspot_id = Column(String(64), primary_key=True)
    city_id = Column(String(32), default="mumbai")
    name = Column(String(255), nullable=False)
    ward = Column(String(128))
    location = Column(Geometry("POINT", srid=4326), nullable=False)
    severity = Column(String(32))
    historical_max_depth_m = Column(Float)
    recurrence = Column(String(64))
    data_source = Column(Text)
    attributes = Column(JSONB, default={})

    __table_args__ = (
        Index("idx_hotspot_geom", location, postgresql_using="gist"),
    )

