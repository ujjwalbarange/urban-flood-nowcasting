-- ============================================================================
-- MUMBAI URBAN FLOOD NOWCASTING & DATA FOUNDATION PLATFORM (MUFNS)
-- PostgreSQL 18 + PostGIS 3.6 Standardized Spatial Schema DDL
-- ============================================================================

-- Ensure PostGIS and UUID extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- 1. ADMINISTRATIVE & BOUNDARIES
-- ============================================================================

CREATE TABLE IF NOT EXISTS cities (
    city_id VARCHAR(32) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    state VARCHAR(128) DEFAULT 'Maharashtra',
    country VARCHAR(4) DEFAULT 'IN',
    crs_epsg INTEGER NOT NULL DEFAULT 4326,
    cell_size_m DOUBLE PRECISION DEFAULT 30.0,
    bbox GEOMETRY(POLYGON, 4326),
    timezone VARCHAR(64) DEFAULT 'Asia/Kolkata',
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS zones (
    zone_id VARCHAR(32) PRIMARY KEY,
    city_id VARCHAR(32) REFERENCES cities(city_id),
    name VARCHAR(128) NOT NULL,
    geometry GEOMETRY(MULTIPOLYGON, 4326),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_zones_geom ON zones USING GIST (geometry);

CREATE TABLE IF NOT EXISTS wards (
    ward_id VARCHAR(32) PRIMARY KEY,
    city_id VARCHAR(32) REFERENCES cities(city_id),
    zone_id VARCHAR(32),
    name VARCHAR(255) NOT NULL,
    geometry GEOMETRY(MULTIPOLYGON, 4326) NOT NULL,
    area_sq_km DOUBLE PRECISION,
    population_2011 INTEGER,
    population_projected INTEGER,
    density_per_sq_km DOUBLE PRECISION,
    chronic_hotspots_count INTEGER DEFAULT 0,
    hazard_score DOUBLE PRECISION,
    exposure_score DOUBLE PRECISION,
    vulnerability_score DOUBLE PRECISION,
    composite_risk_score DOUBLE PRECISION,
    metadata JSONB DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_wards_geom ON wards USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_wards_city ON wards (city_id);

-- ============================================================================
-- 2. TERRAIN & ELEVATION
-- ============================================================================

CREATE TABLE IF NOT EXISTS dem_tiles (
    tile_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    city_id VARCHAR(32) REFERENCES cities(city_id),
    product_name VARCHAR(128) NOT NULL, -- e.g. 'Copernicus GLO-30 DSM', 'CartoDEM V3'
    resolution_m DOUBLE PRECISION NOT NULL,
    width_pixels INTEGER NOT NULL,
    height_pixels INTEGER NOT NULL,
    crs_epsg INTEGER NOT NULL DEFAULT 4326,
    bounds GEOMETRY(POLYGON, 4326) NOT NULL,
    storage_path TEXT NOT NULL,
    sha256 VARCHAR(64),
    min_elevation_m DOUBLE PRECISION,
    max_elevation_m DOUBLE PRECISION,
    mean_elevation_m DOUBLE PRECISION,
    source_url TEXT,
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    provenance JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_dem_bounds ON dem_tiles USING GIST (bounds);

CREATE TABLE IF NOT EXISTS terrain_derivatives (
    derivative_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    dem_tile_id UUID REFERENCES dem_tiles(tile_id),
    derivative_type VARCHAR(64) NOT NULL, -- 'slope_degrees', 'aspect_degrees', 'd8_flow_dir', 'sinks'
    storage_path TEXT NOT NULL,
    min_value DOUBLE PRECISION,
    max_value DOUBLE PRECISION,
    mean_value DOUBLE PRECISION,
    parameters JSONB DEFAULT '{}',
    derived_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- 3. ATMOSPHERIC & RAINFALL OBSERVATIONS & FORECASTS
-- ============================================================================

CREATE TABLE IF NOT EXISTS weather_observations (
    obs_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    station_id VARCHAR(64) NOT NULL,
    station_name VARCHAR(255),
    ward_id VARCHAR(32),
    location GEOMETRY(POINT, 4326) NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    variable VARCHAR(64) NOT NULL, -- 'temperature', 'humidity', 'pressure', 'wind_speed', 'cloud_cover'
    value DOUBLE PRECISION,
    unit VARCHAR(32) NOT NULL,
    source VARCHAR(64) NOT NULL, -- 'Open-Meteo', 'IMD AWS'
    model VARCHAR(64),
    quality_flag VARCHAR(32) DEFAULT 'VALID',
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_weather_obs_time ON weather_observations (observed_at);
CREATE INDEX IF NOT EXISTS idx_weather_obs_var ON weather_observations (variable, observed_at);
CREATE INDEX IF NOT EXISTS idx_weather_obs_loc ON weather_observations USING GIST (location);

CREATE TABLE IF NOT EXISTS weather_forecasts (
    forecast_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    station_id VARCHAR(64) NOT NULL,
    station_name VARCHAR(255),
    ward_id VARCHAR(32),
    location GEOMETRY(POINT, 4326) NOT NULL,
    forecast_generated_at TIMESTAMPTZ NOT NULL,
    forecast_valid_time TIMESTAMPTZ NOT NULL,
    lead_minutes INTEGER NOT NULL,
    variable VARCHAR(64) NOT NULL,
    value DOUBLE PRECISION,
    unit VARCHAR(32) NOT NULL,
    source VARCHAR(64) NOT NULL,
    model VARCHAR(64),
    quality_flag VARCHAR(32) DEFAULT 'FORECAST',
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_weather_fcst_valid ON weather_forecasts (forecast_valid_time);
CREATE INDEX IF NOT EXISTS idx_weather_fcst_gen ON weather_forecasts (forecast_generated_at, lead_minutes);

CREATE TABLE IF NOT EXISTS rainfall_observations (
    obs_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    station_id VARCHAR(64) NOT NULL,
    station_name VARCHAR(255),
    ward_id VARCHAR(32),
    location GEOMETRY(POINT, 4326) NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    rate_mmh DOUBLE PRECISION,
    accumulated_1h_mm DOUBLE PRECISION,
    accumulated_3h_mm DOUBLE PRECISION,
    accumulated_24h_mm DOUBLE PRECISION,
    source VARCHAR(64) NOT NULL, -- 'IMD_AWS', 'Open-Meteo', 'MCGM_Gauge'
    quality_flag VARCHAR(32) DEFAULT 'OBSERVED',
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rain_obs_time ON rainfall_observations (observed_at);
CREATE INDEX IF NOT EXISTS idx_rain_obs_loc ON rainfall_observations USING GIST (location);

CREATE TABLE IF NOT EXISTS rainfall_forecasts (
    forecast_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    station_id VARCHAR(64) NOT NULL,
    ward_id VARCHAR(32),
    location GEOMETRY(POINT, 4326) NOT NULL,
    forecast_generated_at TIMESTAMPTZ NOT NULL,
    forecast_valid_time TIMESTAMPTZ NOT NULL,
    lead_minutes INTEGER NOT NULL,
    rate_mmh DOUBLE PRECISION,
    precipitation_probability_pct DOUBLE PRECISION,
    source VARCHAR(64) NOT NULL,
    model VARCHAR(64),
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_rain_fcst_valid ON rainfall_forecasts (forecast_valid_time);

CREATE TABLE IF NOT EXISTS rainfall_satellite (
    granule_id VARCHAR(128) PRIMARY KEY,
    satellite_mission VARCHAR(64) NOT NULL, -- 'GPM_IMERG', 'INSAT_3DR_HEM'
    product_version VARCHAR(64) NOT NULL,
    granule_timestamp TIMESTAMPTZ NOT NULL,
    run_type VARCHAR(32), -- 'Early', 'Late', 'Final', 'NRT'
    bounds GEOMETRY(POLYGON, 4326),
    mean_precipitation_mmh DOUBLE PRECISION,
    max_precipitation_mmh DOUBLE PRECISION,
    storage_uri TEXT,
    sha256 VARCHAR(64),
    metadata JSONB DEFAULT '{}',
    retrieved_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sat_rain_time ON rainfall_satellite (granule_timestamp);

-- ============================================================================
-- 4. HYDROLOGY, WATER BODIES & DRAINAGE NETWORK
-- ============================================================================

CREATE TABLE IF NOT EXISTS water_bodies (
    water_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255),
    water_type VARCHAR(64) NOT NULL, -- 'lake', 'pond', 'reservoir', 'creek', 'estuary'
    geometry GEOMETRY(MULTIPOLYGON, 4326) NOT NULL,
    area_sq_km DOUBLE PRECISION,
    full_reservoir_level_m DOUBLE PRECISION,
    source VARCHAR(64) DEFAULT 'OpenStreetMap',
    attributes JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_water_bodies_geom ON water_bodies USING GIST (geometry);

CREATE TABLE IF NOT EXISTS rivers (
    river_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL, -- 'Mithi River', 'Poisar River', 'Dahisar River', 'Oshiwara River'
    geometry GEOMETRY(MULTILINESTRING, 4326) NOT NULL,
    length_km DOUBLE PRECISION,
    catchment_name VARCHAR(128),
    channel_type VARCHAR(64) DEFAULT 'natural_and_concretized',
    attributes JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_rivers_geom ON rivers USING GIST (geometry);

CREATE TABLE IF NOT EXISTS drainage_nodes (
    node_id VARCHAR(64) PRIMARY KEY,
    city_id VARCHAR(32) REFERENCES cities(city_id),
    name VARCHAR(255),
    node_type VARCHAR(64) NOT NULL, -- 'holding_pond', 'drop_inlet', 'manhole', 'junction', 'outfall'
    geometry GEOMETRY(POINT, 4326) NOT NULL,
    invert_elevation_m DOUBLE PRECISION,
    ground_elevation_m DOUBLE PRECISION,
    catchment VARCHAR(128),
    holding_capacity_m3 DOUBLE PRECISION,
    data_quality VARCHAR(32) DEFAULT 'static_engineering_inventory',
    attributes JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_drain_nodes_geom ON drainage_nodes USING GIST (geometry);

CREATE TABLE IF NOT EXISTS drainage_links (
    link_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255),
    from_node VARCHAR(64) REFERENCES drainage_nodes(node_id),
    to_node VARCHAR(64) REFERENCES drainage_nodes(node_id),
    link_type VARCHAR(64), -- 'open_nullah', 'box_culvert', 'pipe'
    geometry GEOMETRY(LINESTRING, 4326) NOT NULL,
    width_m DOUBLE PRECISION,
    depth_m DOUBLE PRECISION,
    length_m DOUBLE PRECISION,
    manning_n DOUBLE PRECISION DEFAULT 0.025,
    slope DOUBLE PRECISION,
    attributes JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_drain_links_geom ON drainage_links USING GIST (geometry);

CREATE TABLE IF NOT EXISTS pumping_stations (
    pump_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    ward VARCHAR(128),
    location GEOMETRY(POINT, 4326) NOT NULL,
    num_pumps INTEGER DEFAULT 6,
    rated_capacity_m3_s DOUBLE PRECISION NOT NULL,
    catchment_area VARCHAR(128),
    current_status VARCHAR(32) DEFAULT 'operational',
    outfall_waterbody VARCHAR(128) DEFAULT 'Arabian Sea',
    data_source VARCHAR(128) DEFAULT 'BRIMSTOWAD Master Plan (Static Rated Capacity)',
    attributes JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_pumps_geom ON pumping_stations USING GIST (location);

CREATE TABLE IF NOT EXISTS tide_observations (
    tide_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    station_name VARCHAR(128) DEFAULT 'Apollo Bunder (Gateway of India)',
    timestamp TIMESTAMPTZ NOT NULL,
    height_m_cd DOUBLE PRECISION NOT NULL, -- Chart Datum
    height_m_msl DOUBLE PRECISION NOT NULL, -- Mean Sea Level (MSL = CD - 2.51m)
    tide_phase VARCHAR(32), -- 'HIGH_TIDE', 'LOW_TIDE', 'RISING', 'FALLING'
    astronomical_prediction_m DOUBLE PRECISION,
    meteorological_surge_m DOUBLE PRECISION,
    source VARCHAR(128) DEFAULT 'Survey of India / Mumbai Port Trust',
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tide_time ON tide_observations (timestamp);

-- ============================================================================
-- 5. EXPOSURE: BUILDINGS, POPULATION, ROADS, INFRASTRUCTURE, SHELTERS
-- ============================================================================

CREATE TABLE IF NOT EXISTS buildings (
    building_id VARCHAR(64) PRIMARY KEY,
    ward_id VARCHAR(32) REFERENCES wards(ward_id),
    geometry GEOMETRY(POLYGON, 4326) NOT NULL,
    area_sq_m DOUBLE PRECISION,
    height_m DOUBLE PRECISION, -- NULL if unavailable
    num_floors INTEGER, -- NULL if unavailable
    building_type VARCHAR(64) DEFAULT 'general',
    ground_elevation_m DOUBLE PRECISION,
    source VARCHAR(64) NOT NULL, -- 'OpenStreetMap', 'Microsoft_ML_Footprints'
    attributes JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_buildings_geom ON buildings USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_buildings_ward ON buildings (ward_id);

CREATE TABLE IF NOT EXISTS population_grids (
    grid_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ward_id VARCHAR(32),
    bounds GEOMETRY(POLYGON, 4326) NOT NULL,
    resolution_m DOUBLE PRECISION DEFAULT 100.0,
    population_count DOUBLE PRECISION NOT NULL,
    density_per_sq_km DOUBLE PRECISION,
    epoch_year INTEGER DEFAULT 2021,
    source VARCHAR(64) DEFAULT 'WorldPop / Census 2011 Projection'
);
CREATE INDEX IF NOT EXISTS idx_pop_grid_geom ON population_grids USING GIST (bounds);

CREATE TABLE IF NOT EXISTS road_segments (
    segment_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255),
    road_class VARCHAR(64) NOT NULL, -- 'motorway', 'trunk', 'primary', 'secondary', 'subway'
    geometry GEOMETRY(LINESTRING, 4326) NOT NULL,
    length_m DOUBLE PRECISION,
    elevation_m DOUBLE PRECISION,
    is_underpass BOOLEAN DEFAULT FALSE,
    flood_vulnerability VARCHAR(32) DEFAULT 'moderate',
    osm_id BIGINT,
    attributes JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_roads_geom ON road_segments USING GIST (geometry);

CREATE TABLE IF NOT EXISTS critical_infrastructure (
    infra_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(64) NOT NULL, -- 'hospital', 'fire_station', 'police', 'substation', 'railway_terminus'
    ward VARCHAR(128),
    location GEOMETRY(POINT, 4326) NOT NULL,
    elevation_m DOUBLE PRECISION,
    capacity INTEGER,
    flood_vulnerable BOOLEAN DEFAULT FALSE,
    source VARCHAR(128) DEFAULT 'MCGM GIS / OpenStreetMap',
    attributes JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_infra_geom ON critical_infrastructure USING GIST (location);

CREATE TABLE IF NOT EXISTS shelters (
    shelter_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    ward VARCHAR(128) NOT NULL,
    address TEXT,
    location GEOMETRY(POINT, 4326) NOT NULL,
    capacity_persons INTEGER,
    elevation_m DOUBLE PRECISION,
    backup_power_generator VARCHAR(32) DEFAULT 'unknown',
    medical_first_aid_post VARCHAR(32) DEFAULT 'unknown',
    operational_status VARCHAR(32) DEFAULT 'operational',
    source VARCHAR(128) DEFAULT 'MCGM Disaster Management Registry',
    last_verified DATE
);
CREATE INDEX IF NOT EXISTS idx_shelters_geom ON shelters USING GIST (location);

-- ============================================================================
-- 6. HISTORICAL FLOOD EVENTS & FIELD OBSERVATIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS historical_flood_events (
    event_id VARCHAR(64) PRIMARY KEY,
    date TIMESTAMPTZ NOT NULL,
    year INTEGER NOT NULL,
    ward VARCHAR(128) NOT NULL,
    locality TEXT NOT NULL,
    location GEOMETRY(POINT, 4326) NOT NULL,
    elevation_m DOUBLE PRECISION,
    slope_degree DOUBLE PRECISION,
    distance_to_drain_m DOUBLE PRECISION,
    distance_to_waterbody_m DOUBLE PRECISION,
    rainfall_1h_mm DOUBLE PRECISION,
    rainfall_3h_mm DOUBLE PRECISION,
    rainfall_6h_mm DOUBLE PRECISION,
    rainfall_12h_mm DOUBLE PRECISION,
    rainfall_24h_mm DOUBLE PRECISION,
    rainfall_48h_mm DOUBLE PRECISION,
    rainfall_72h_mm DOUBLE PRECISION,
    rainfall_intensity_mm_h DOUBLE PRECISION,
    soil_moisture DOUBLE PRECISION,
    soil_type VARCHAR(128),
    infiltration_rate DOUBLE PRECISION,
    drain_water_level_m DOUBLE PRECISION,
    built_up_percentage DOUBLE PRECISION,
    impervious_surface_percentage DOUBLE PRECISION,
    drainage_capacity DOUBLE PRECISION,
    ndvi DOUBLE PRECISION,
    ndwi DOUBLE PRECISION,
    ndbi DOUBLE PRECISION,
    flooded_area_km2 DOUBLE PRECISION,
    flood_occurred BOOLEAN DEFAULT TRUE,
    flood_depth_cm DOUBLE PRECISION,
    flood_duration_hours DOUBLE PRECISION,
    waterlogging_duration_hours DOUBLE PRECISION,
    flood_severity VARCHAR(32),
    people_affected INTEGER,
    houses_affected INTEGER,
    roads_affected INTEGER,
    economic_loss DOUBLE PRECISION,
    rainfall_intensity_index DOUBLE PRECISION,
    drainage_stress_index DOUBLE PRECISION,
    imperviousness_index DOUBLE PRECISION,
    data_source TEXT,
    data_type VARCHAR(32) DEFAULT 'observed',
    ingested_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_hist_flood_geom ON historical_flood_events USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_hist_flood_date ON historical_flood_events (date);
CREATE INDEX IF NOT EXISTS idx_hist_flood_ward ON historical_flood_events (ward);

CREATE TABLE IF NOT EXISTS flood_hotspots (
    hotspot_id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    ward VARCHAR(128) NOT NULL,
    location GEOMETRY(POINT, 4326) NOT NULL,
    drainage_basin VARCHAR(128),
    typical_water_depth_m DOUBLE PRECISION,
    maximum_recorded_depth_m DOUBLE PRECISION,
    traffic_impact VARCHAR(64),
    mitigation_status TEXT,
    recurrence VARCHAR(64) DEFAULT 'every_monsoon',
    data_source VARCHAR(128) DEFAULT 'MCGM Chronic Flood Spot Registry'
);
CREATE INDEX IF NOT EXISTS idx_hotspots_geom ON flood_hotspots USING GIST (location);

CREATE TABLE IF NOT EXISTS citizen_reports (
    report_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reporter_name VARCHAR(255),
    location GEOMETRY(POINT, 4326) NOT NULL,
    location_name VARCHAR(255),
    ward_id VARCHAR(32),
    water_depth_cm DOUBLE PRECISION,
    category VARCHAR(64) DEFAULT 'waterlogging',
    severity VARCHAR(32) DEFAULT 'moderate',
    road_condition VARCHAR(64),
    vehicle_accessibility VARCHAR(64),
    description TEXT,
    photo_url TEXT,
    verified BOOLEAN DEFAULT FALSE,
    verification_status VARCHAR(32) DEFAULT 'pending',
    reported_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    verified_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_citizen_reports_geom ON citizen_reports USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_citizen_reports_time ON citizen_reports (reported_at);

-- ============================================================================
-- 7. AUDIT, DATA QUALITY & PROVENANCE
-- ============================================================================

CREATE TABLE IF NOT EXISTS data_sources (
    source_id VARCHAR(64) PRIMARY KEY,
    provider_name VARCHAR(255) NOT NULL,
    dataset_name VARCHAR(255) NOT NULL,
    url TEXT,
    access_method VARCHAR(128),
    license VARCHAR(255),
    spatial_coverage TEXT,
    spatial_resolution VARCHAR(64),
    temporal_resolution VARCHAR(64),
    crs VARCHAR(32) DEFAULT 'EPSG:4326',
    status VARCHAR(32) DEFAULT 'active',
    last_successful_fetch TIMESTAMPTZ,
    error_message TEXT,
    config JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS data_ingestion_runs (
    run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id VARCHAR(64) REFERENCES data_sources(source_id),
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status VARCHAR(32) NOT NULL, -- 'SUCCESS', 'FAILED', 'PARTIAL'
    records_ingested INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    file_path TEXT,
    sha256 VARCHAR(64),
    error_details TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS data_quality_checks (
    check_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(128) NOT NULL,
    checked_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    total_records INTEGER NOT NULL,
    null_geometry_count INTEGER DEFAULT 0,
    invalid_geometry_count INTEGER DEFAULT 0,
    out_of_bounds_count INTEGER DEFAULT 0,
    duplicate_records_count INTEGER DEFAULT 0,
    status VARCHAR(32) NOT NULL, -- 'PASSED', 'WARNING', 'FAILED'
    details JSONB DEFAULT '{}'
);
