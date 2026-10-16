-- ============================================================================
-- MUMBAI URBAN FLOOD NOWCASTING & DATA FOUNDATION PLATFORM (MUFNS)
-- Actual Verified PostgreSQL 18.6 + PostGIS 3.6.4 Database DDL Schema Dump
-- Database Name: defaultdb (Aiven Cloud PostgreSQL)
-- Generated programmatically from information_schema and pg_catalog
-- Date: 2026-09-25
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ------------------------------------------------------------
-- Table: alerts
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."alerts" (
"alert_id" UUID NOT NULL DEFAULT gen_random_uuid(),
"city_id" VARCHAR(255),
"run_id" UUID,
"severity" VARCHAR(255),
"cap_xml" TEXT,
"issued_at" TIMESTAMPTZ  DEFAULT now(),
"expires_at" TIMESTAMPTZ,
"affected_area" geometry(POLYGON, 4326),
"affected_wards" _TEXT,
"metadata" JSONB
);

CREATE UNIQUE INDEX alerts_pkey ON public.alerts USING btree (alert_id);
CREATE INDEX idx_alerts_affected_area ON public.alerts USING gist (affected_area);

-- ------------------------------------------------------------
-- Table: bridges_and_culverts
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."bridges_and_culverts" (
"structure_id" VARCHAR(255) NOT NULL,
"name" VARCHAR(255) NOT NULL,
"structure_type" VARCHAR(255),
"road_name" VARCHAR(255),
"waterway_name" VARCHAR(255),
"source" TEXT,
"confidence" VARCHAR(255),
"geometry" geometry(GEOMETRY, 4326),
"attributes" JSONB,
"created_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX bridges_and_culverts_pkey ON public.bridges_and_culverts USING btree (structure_id);
CREATE INDEX idx_bridges_culverts_geom ON public.bridges_and_culverts USING gist (geometry);

-- ------------------------------------------------------------
-- Table: buildings
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."buildings" (
"building_id" VARCHAR(255) NOT NULL,
"source_id" VARCHAR(255),
"source" VARCHAR(255) NOT NULL,
"geometry" geometry(POLYGON, 4326) NOT NULL,
"centroid" geometry(POINT, 4326),
"area_sq_m" DOUBLE PRECISION,
"building_type" VARCHAR(255),
"confidence" DOUBLE PRECISION,
"ward_id" VARCHAR(255),
"locality" VARCHAR(255),
"height_m" DOUBLE PRECISION,
"floor_count" INTEGER,
"occupancy" INTEGER,
"plinth_height_m" DOUBLE PRECISION,
"quadkey" VARCHAR(255),
"ingested_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX buildings_pkey ON public.buildings USING btree (building_id);
CREATE INDEX idx_buildings_geom ON public.buildings USING gist (geometry);
CREATE INDEX idx_buildings_centroid ON public.buildings USING gist (centroid);
CREATE INDEX idx_buildings_ward ON public.buildings USING btree (ward_id);

-- ------------------------------------------------------------
-- Table: cities
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."cities" (
"city_id" VARCHAR(255) NOT NULL,
"name" VARCHAR(255) NOT NULL,
"state" VARCHAR(255),
"country" VARCHAR(255),
"crs_epsg" INTEGER NOT NULL,
"cell_size_m" DOUBLE PRECISION,
"bbox" geometry(POLYGON, 4326),
"timezone" VARCHAR(255),
"config" JSONB,
"created_at" TIMESTAMPTZ  DEFAULT now()
);

CREATE UNIQUE INDEX cities_pkey ON public.cities USING btree (city_id);
CREATE INDEX idx_cities_bbox ON public.cities USING gist (bbox);

-- ------------------------------------------------------------
-- Table: citizen_reports
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."citizen_reports" (
"report_id" UUID NOT NULL DEFAULT gen_random_uuid(),
"city_id" VARCHAR(255),
"reporter_name" VARCHAR(255),
"location" geometry(POINT, 4326) NOT NULL,
"ward_id" VARCHAR(255),
"reported_at" TIMESTAMPTZ  DEFAULT now(),
"water_depth_cm" DOUBLE PRECISION,
"description" TEXT,
"photo_url" TEXT,
"report_type" VARCHAR(255),
"verification_status" VARCHAR(255),
"metadata" JSONB
);

CREATE UNIQUE INDEX citizen_reports_pkey ON public.citizen_reports USING btree (report_id);
CREATE INDEX idx_reports_geom ON public.citizen_reports USING gist (location);
CREATE INDEX idx_citizen_reports_location ON public.citizen_reports USING gist (location);
CREATE INDEX idx_reports_time ON public.citizen_reports USING btree (reported_at);

-- ------------------------------------------------------------
-- Table: coastal_exposure_zones
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."coastal_exposure_zones" (
"zone_id" VARCHAR(255) NOT NULL,
"name" VARCHAR(255) NOT NULL,
"zone_type" VARCHAR(255),
"source" TEXT,
"confidence" VARCHAR(255),
"geometry" geometry(GEOMETRY, 4326),
"attributes" JSONB,
"created_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX coastal_exposure_zones_pkey ON public.coastal_exposure_zones USING btree (zone_id);
CREATE INDEX idx_coastal_exposure_geom ON public.coastal_exposure_zones USING gist (geometry);

-- ------------------------------------------------------------
-- Table: critical_arterial_corridors
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."critical_arterial_corridors" (
"corridor_id" VARCHAR(255) NOT NULL,
"name" VARCHAR(255) NOT NULL,
"highway" VARCHAR(255),
"surface" VARCHAR(255),
"lanes" INTEGER,
"length_m" DOUBLE PRECISION,
"bridge" VARCHAR(255),
"tunnel" VARCHAR(255),
"one_way" VARCHAR(255),
"maxspeed" VARCHAR(255),
"ward_id" VARCHAR(255),
"source" TEXT,
"confidence" VARCHAR(255),
"geometry" geometry(GEOMETRY, 4326),
"attributes" JSONB,
"created_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX critical_arterial_corridors_pkey ON public.critical_arterial_corridors USING btree (corridor_id);
CREATE INDEX idx_critical_corridors_geom ON public.critical_arterial_corridors USING gist (geometry);

-- ------------------------------------------------------------
-- Table: critical_infrastructure
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."critical_infrastructure" (
"infra_id" VARCHAR(255) NOT NULL,
"city_id" VARCHAR(255),
"name" VARCHAR(255) NOT NULL,
"category" VARCHAR(255),
"ward" VARCHAR(255),
"location" geometry(POINT, 4326) NOT NULL,
"capacity" INTEGER,
"elevation_m" DOUBLE PRECISION,
"flood_vulnerable" BOOLEAN,
"data_source" TEXT,
"attributes" JSONB
);

CREATE UNIQUE INDEX critical_infrastructure_pkey ON public.critical_infrastructure USING btree (infra_id);
CREATE INDEX idx_critical_infrastructure_location ON public.critical_infrastructure USING gist (location);
CREATE INDEX idx_infra_geom ON public.critical_infrastructure USING gist (location);

-- ------------------------------------------------------------
-- Table: data_ingestion_runs
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."data_ingestion_runs" (
"run_id" UUID NOT NULL DEFAULT gen_random_uuid(),
"pipeline_name" VARCHAR(255) NOT NULL,
"source_id" VARCHAR(255) NOT NULL,
"records_ingested" INTEGER  DEFAULT 0,
"records_failed" INTEGER  DEFAULT 0,
"status" VARCHAR(255) NOT NULL,
"started_at" TIMESTAMPTZ NOT NULL,
"completed_at" TIMESTAMPTZ,
"log_summary" JSONB  DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX data_ingestion_runs_pkey ON public.data_ingestion_runs USING btree (run_id);

-- ------------------------------------------------------------
-- Table: data_sources
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."data_sources" (
"source_id" VARCHAR(255) NOT NULL,
"provider_name" VARCHAR(255) NOT NULL,
"provider_type" VARCHAR(255),
"description" TEXT,
"url" TEXT,
"license" VARCHAR(255),
"spatial_resolution" VARCHAR(255),
"temporal_resolution" VARCHAR(255),
"crs" VARCHAR(255),
"status" VARCHAR(255),
"last_successful_fetch" TIMESTAMPTZ,
"error_message" TEXT,
"config" JSONB
);

CREATE UNIQUE INDEX data_sources_pkey ON public.data_sources USING btree (source_id);

-- ------------------------------------------------------------
-- Table: dem_tiles
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."dem_tiles" (
"tile_id" UUID NOT NULL DEFAULT gen_random_uuid(),
"city_id" VARCHAR(255),
"source" VARCHAR(255),
"crs_epsg" INTEGER NOT NULL,
"resolution_m" DOUBLE PRECISION NOT NULL,
"width" INTEGER NOT NULL,
"height" INTEGER NOT NULL,
"bounds" geometry(POLYGON, 4326),
"storage_uri" TEXT NOT NULL,
"sha256" VARCHAR(255),
"ingested_at" TIMESTAMPTZ  DEFAULT now(),
"provenance" JSONB,
"product_name" VARCHAR(255),
"min_elevation_m" DOUBLE PRECISION,
"max_elevation_m" DOUBLE PRECISION,
"mean_elevation_m" DOUBLE PRECISION,
"source_url" TEXT,
"storage_path" TEXT,
"width_pixels" INTEGER,
"height_pixels" INTEGER
);

CREATE UNIQUE INDEX dem_tiles_pkey ON public.dem_tiles USING btree (tile_id);
CREATE INDEX idx_dem_tiles_bounds ON public.dem_tiles USING gist (bounds);

-- ------------------------------------------------------------
-- Table: drainage_links
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."drainage_links" (
"link_id" VARCHAR(255) NOT NULL,
"city_id" VARCHAR(255),
"from_node" VARCHAR(255),
"to_node" VARCHAR(255),
"link_type" VARCHAR(255),
"geometry" geometry(LINESTRING, 4326),
"diameter_m" DOUBLE PRECISION,
"length_m" DOUBLE PRECISION,
"manning_n" DOUBLE PRECISION,
"data_quality" VARCHAR(255),
"attributes" JSONB
);

CREATE UNIQUE INDEX drainage_links_pkey ON public.drainage_links USING btree (link_id);
CREATE INDEX idx_drainage_links_geometry ON public.drainage_links USING gist (geometry);

-- ------------------------------------------------------------
-- Table: drainage_nodes
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."drainage_nodes" (
"node_id" VARCHAR(255) NOT NULL,
"city_id" VARCHAR(255),
"node_type" VARCHAR(255),
"geometry" geometry(POINT, 4326) NOT NULL,
"invert_elevation_m" DOUBLE PRECISION,
"ground_elevation_m" DOUBLE PRECISION,
"data_quality" VARCHAR(255),
"attributes" JSONB
);

CREATE UNIQUE INDEX drainage_nodes_pkey ON public.drainage_nodes USING btree (node_id);
CREATE INDEX idx_drain_nodes_geom ON public.drainage_nodes USING gist (geometry);
CREATE INDEX idx_drainage_nodes_geometry ON public.drainage_nodes USING gist (geometry);

-- ------------------------------------------------------------
-- Table: drainage_structures
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."drainage_structures" (
"structure_id" VARCHAR(255) NOT NULL,
"name" VARCHAR(255) NOT NULL,
"structure_type" VARCHAR(255),
"connected_drainage_id" VARCHAR(255),
"ward_id" VARCHAR(255),
"source" TEXT,
"confidence" VARCHAR(255),
"geometry" geometry(GEOMETRY, 4326),
"attributes" JSONB,
"created_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX drainage_structures_pkey ON public.drainage_structures USING btree (structure_id);
CREATE INDEX idx_drainage_structures_geom ON public.drainage_structures USING gist (geometry);

-- ------------------------------------------------------------
-- Table: emergency_facilities
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."emergency_facilities" (
"infra_id" VARCHAR(255),
"city_id" VARCHAR(255),
"name" VARCHAR(255),
"category" VARCHAR(255),
"ward" VARCHAR(255),
"location" geometry(POINT, 4326),
"capacity" INTEGER,
"elevation_m" DOUBLE PRECISION,
"flood_vulnerable" BOOLEAN,
"data_source" TEXT,
"attributes" JSONB
);

CREATE INDEX idx_emergency_facilities_loc ON public.emergency_facilities USING gist (location);
CREATE INDEX idx_emergency_facilities_ward ON public.emergency_facilities USING btree (ward);

-- ------------------------------------------------------------
-- Table: fire_stations
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."fire_stations" (
"infra_id" VARCHAR(255),
"city_id" VARCHAR(255),
"name" VARCHAR(255),
"category" VARCHAR(255),
"ward" VARCHAR(255),
"location" geometry(POINT, 4326),
"capacity" INTEGER,
"elevation_m" DOUBLE PRECISION,
"flood_vulnerable" BOOLEAN,
"data_source" TEXT,
"attributes" JSONB
);

CREATE INDEX idx_fire_stations_loc ON public.fire_stations USING gist (location);
CREATE INDEX idx_fire_stations_ward ON public.fire_stations USING btree (ward);

-- ------------------------------------------------------------
-- Table: flood_hotspots
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."flood_hotspots" (
"hotspot_id" VARCHAR(255) NOT NULL,
"city_id" VARCHAR(255)  DEFAULT 'mumbai'::character varying,
"name" VARCHAR(255) NOT NULL,
"ward" VARCHAR(255),
"hotspot_type" VARCHAR(255),
"severity" VARCHAR(255),
"recurrence" VARCHAR(255),
"historical_max_depth_m" DOUBLE PRECISION,
"typical_water_depth_m" DOUBLE PRECISION,
"traffic_impact" TEXT,
"railway_impact" TEXT,
"mitigation_status" TEXT,
"drainage_basin" VARCHAR(255),
"nearby_events_count" INTEGER  DEFAULT 0,
"evidence" TEXT,
"source" TEXT,
"source_url" TEXT,
"confidence" VARCHAR(255),
"location" geometry(POINT, 4326),
"attributes" JSONB,
"created_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX flood_hotspots_new_pkey ON public.flood_hotspots USING btree (hotspot_id);
CREATE INDEX idx_flood_hotspots_new_geom ON public.flood_hotspots USING gist (location);

-- ------------------------------------------------------------
-- Table: flood_hotspots_v1_legacy
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."flood_hotspots_v1_legacy" (
"hotspot_id" VARCHAR(255),
"city_id" VARCHAR(255),
"name" VARCHAR(255),
"ward" VARCHAR(255),
"location" geometry(POINT, 4326),
"severity" VARCHAR(255),
"historical_max_depth_m" DOUBLE PRECISION,
"recurrence" VARCHAR(255),
"data_source" TEXT,
"attributes" JSONB
);


-- ------------------------------------------------------------
-- Table: flood_snapshots
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."flood_snapshots" (
"snapshot_id" UUID NOT NULL DEFAULT gen_random_uuid(),
"run_id" UUID,
"valid_time" TIMESTAMPTZ NOT NULL,
"lead_minutes" INTEGER,
"max_depth_m" DOUBLE PRECISION,
"mean_depth_m" DOUBLE PRECISION,
"flooded_cells" INTEGER,
"flooded_area_m2" DOUBLE PRECISION,
"extent_threshold_m" DOUBLE PRECISION,
"depth_grid_uri" TEXT,
"statistics" JSONB
);

CREATE UNIQUE INDEX flood_snapshots_pkey ON public.flood_snapshots USING btree (snapshot_id);

-- ------------------------------------------------------------
-- Table: green_open_spaces
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."green_open_spaces" (
"space_id" VARCHAR(255) NOT NULL,
"name" VARCHAR(255) NOT NULL,
"category" VARCHAR(255),
"area_m2" DOUBLE PRECISION,
"source" TEXT,
"confidence" VARCHAR(255),
"geometry" geometry(GEOMETRY, 4326),
"attributes" JSONB,
"created_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX green_open_spaces_pkey ON public.green_open_spaces USING btree (space_id);
CREATE INDEX idx_green_spaces_geom ON public.green_open_spaces USING gist (geometry);

-- ------------------------------------------------------------
-- Table: historical_flood_events
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."historical_flood_events" (
"event_id" VARCHAR(255) NOT NULL,
"city_id" VARCHAR(255),
"date" TIMESTAMPTZ NOT NULL,
"year" INTEGER,
"ward" VARCHAR(255),
"locality" TEXT,
"location" geometry(POINT, 4326) NOT NULL,
"elevation_m" DOUBLE PRECISION,
"slope_degree" DOUBLE PRECISION,
"distance_to_drain_m" DOUBLE PRECISION,
"distance_to_waterbody_m" DOUBLE PRECISION,
"rainfall_1h_mm" DOUBLE PRECISION,
"rainfall_3h_mm" DOUBLE PRECISION,
"rainfall_6h_mm" DOUBLE PRECISION,
"rainfall_12h_mm" DOUBLE PRECISION,
"rainfall_24h_mm" DOUBLE PRECISION,
"rainfall_48h_mm" DOUBLE PRECISION,
"rainfall_72h_mm" DOUBLE PRECISION,
"rainfall_intensity_mm_h" DOUBLE PRECISION,
"rainfall_anomaly" DOUBLE PRECISION,
"antecedent_rainfall_3day_mm" DOUBLE PRECISION,
"antecedent_rainfall_7day_mm" DOUBLE PRECISION,
"soil_moisture" DOUBLE PRECISION,
"soil_type" VARCHAR(255),
"infiltration_rate" DOUBLE PRECISION,
"groundwater_level_m" DOUBLE PRECISION,
"drain_water_level_m" DOUBLE PRECISION,
"built_up_percentage" DOUBLE PRECISION,
"impervious_surface_percentage" DOUBLE PRECISION,
"vegetation_percentage" DOUBLE PRECISION,
"population_density" DOUBLE PRECISION,
"drainage_capacity" DOUBLE PRECISION,
"ndvi" DOUBLE PRECISION,
"ndwi" DOUBLE PRECISION,
"ndbi" DOUBLE PRECISION,
"flooded_area_km2" DOUBLE PRECISION,
"flood_occurred" BOOLEAN,
"flood_depth_cm" DOUBLE PRECISION,
"flood_duration_hours" DOUBLE PRECISION,
"waterlogging_duration_hours" DOUBLE PRECISION,
"flood_severity" VARCHAR(255),
"people_affected" INTEGER,
"houses_affected" INTEGER,
"roads_affected" INTEGER,
"economic_loss" DOUBLE PRECISION,
"rainfall_intensity_index" DOUBLE PRECISION,
"drainage_stress_index" DOUBLE PRECISION,
"imperviousness_index" DOUBLE PRECISION,
"data_source" TEXT,
"source_url" TEXT,
"data_type" VARCHAR(255),
"ingested_at" TIMESTAMPTZ  DEFAULT now()
);

CREATE UNIQUE INDEX historical_flood_events_pkey ON public.historical_flood_events USING btree (event_id);
CREATE INDEX idx_hist_flood_ward ON public.historical_flood_events USING btree (ward);
CREATE INDEX idx_historical_flood_events_location ON public.historical_flood_events USING gist (location);
CREATE INDEX idx_hist_flood_geom ON public.historical_flood_events USING gist (location);
CREATE INDEX idx_hist_flood_date ON public.historical_flood_events USING btree (date);

-- ------------------------------------------------------------
-- Table: hospitals
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."hospitals" (
"infra_id" VARCHAR(255),
"city_id" VARCHAR(255),
"name" VARCHAR(255),
"healthcare_type" VARCHAR(255),
"ward" VARCHAR(255),
"location" geometry(POINT, 4326),
"capacity" INTEGER,
"elevation_m" DOUBLE PRECISION,
"flood_vulnerable" BOOLEAN,
"data_source" TEXT,
"attributes" JSONB
);

CREATE INDEX idx_hospitals_loc ON public.hospitals USING gist (location);
CREATE INDEX idx_hospitals_ward ON public.hospitals USING btree (ward);

-- ------------------------------------------------------------
-- Table: impervious_surface_grid
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."impervious_surface_grid" (
"cell_id" VARCHAR(255) NOT NULL,
"impervious_fraction" DOUBLE PRECISION NOT NULL,
"built_up_fraction" DOUBLE PRECISION,
"source" TEXT,
"confidence" VARCHAR(255),
"geometry" geometry(GEOMETRY, 4326),
"attributes" JSONB,
"created_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX impervious_surface_grid_pkey ON public.impervious_surface_grid USING btree (cell_id);
CREATE INDEX idx_impervious_surface_geom ON public.impervious_surface_grid USING gist (geometry);

-- ------------------------------------------------------------
-- Table: land_use_land_cover
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."land_use_land_cover" (
"lulc_id" VARCHAR(255) NOT NULL,
"name" VARCHAR(255),
"class" VARCHAR(255) NOT NULL,
"class_code" VARCHAR(255),
"area_m2" DOUBLE PRECISION,
"source" TEXT,
"source_date" VARCHAR(255),
"confidence" VARCHAR(255),
"geometry" geometry(GEOMETRY, 4326),
"attributes" JSONB,
"created_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX land_use_land_cover_pkey ON public.land_use_land_cover USING btree (lulc_id);
CREATE INDEX idx_lulc_geom ON public.land_use_land_cover USING gist (geometry);

-- ------------------------------------------------------------
-- Table: low_lying_areas
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."low_lying_areas" (
"zone_id" VARCHAR(255) NOT NULL,
"name" VARCHAR(255) NOT NULL,
"depression_type" VARCHAR(255),
"elevation_min_m" DOUBLE PRECISION,
"elevation_mean_m" DOUBLE PRECISION,
"area_m2" DOUBLE PRECISION,
"source" TEXT,
"confidence" VARCHAR(255),
"geometry" geometry(GEOMETRY, 4326),
"attributes" JSONB,
"created_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX low_lying_areas_pkey ON public.low_lying_areas USING btree (zone_id);
CREATE INDEX idx_low_lying_geom ON public.low_lying_areas USING gist (geometry);

-- ------------------------------------------------------------
-- Table: police
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."police" (
"infra_id" VARCHAR(255),
"city_id" VARCHAR(255),
"name" VARCHAR(255),
"category" VARCHAR(255),
"ward" VARCHAR(255),
"location" geometry(POINT, 4326),
"capacity" INTEGER,
"elevation_m" DOUBLE PRECISION,
"flood_vulnerable" BOOLEAN,
"data_source" TEXT,
"attributes" JSONB
);

CREATE INDEX idx_police_loc ON public.police USING gist (location);
CREATE INDEX idx_police_ward ON public.police USING btree (ward);

-- ------------------------------------------------------------
-- Table: population_grids
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."population_grids" (
"grid_id" VARCHAR(255) NOT NULL,
"geometry" geometry(POLYGON, 4326) NOT NULL,
"centroid" geometry(POINT, 4326) NOT NULL,
"population_count" DOUBLE PRECISION NOT NULL,
"density_per_sq_km" DOUBLE PRECISION NOT NULL,
"resolution_m" DOUBLE PRECISION NOT NULL,
"year" INTEGER NOT NULL,
"source" VARCHAR(255) NOT NULL,
"crs_epsg" INTEGER NOT NULL DEFAULT 4326,
"ward_id" VARCHAR(255),
"ingested_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX population_grids_pkey ON public.population_grids USING btree (grid_id);
CREATE INDEX idx_pop_grid_geom ON public.population_grids USING gist (geometry);
CREATE INDEX idx_pop_grid_centroid ON public.population_grids USING gist (centroid);
CREATE INDEX idx_pop_grid_ward ON public.population_grids USING btree (ward_id);

-- ------------------------------------------------------------
-- Table: primary_drainage_network
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."primary_drainage_network" (
"drainage_id" VARCHAR(255) NOT NULL,
"name" VARCHAR(255) NOT NULL,
"drainage_type" VARCHAR(255),
"length_m" DOUBLE PRECISION,
"ward_id" VARCHAR(255),
"source" TEXT,
"source_date" VARCHAR(255),
"confidence" VARCHAR(255),
"geometry" geometry(GEOMETRY, 4326),
"attributes" JSONB,
"created_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX primary_drainage_network_pkey ON public.primary_drainage_network USING btree (drainage_id);
CREATE INDEX idx_primary_drainage_geom ON public.primary_drainage_network USING gist (geometry);

-- ------------------------------------------------------------
-- Table: pumping_stations
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."pumping_stations" (
"pump_id" VARCHAR(255) NOT NULL,
"city_id" VARCHAR(255),
"name" VARCHAR(255) NOT NULL,
"ward" VARCHAR(255),
"location" geometry(POINT, 4326) NOT NULL,
"num_pumps" INTEGER,
"rated_capacity_mld" DOUBLE PRECISION,
"current_status" VARCHAR(255),
"operational_capacity_pct" DOUBLE PRECISION,
"data_source" TEXT,
"last_updated" TIMESTAMPTZ  DEFAULT now(),
"attributes" JSONB
);

CREATE UNIQUE INDEX pumping_stations_pkey ON public.pumping_stations USING btree (pump_id);
CREATE INDEX idx_pumping_stations_location ON public.pumping_stations USING gist (location);

-- ------------------------------------------------------------
-- Table: railway_stations
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."railway_stations" (
"infra_id" VARCHAR(255),
"city_id" VARCHAR(255),
"name" VARCHAR(255),
"category" VARCHAR(255),
"ward" VARCHAR(255),
"location" geometry(POINT, 4326),
"capacity" INTEGER,
"elevation_m" DOUBLE PRECISION,
"flood_vulnerable" BOOLEAN,
"data_source" TEXT,
"attributes" JSONB
);

CREATE INDEX idx_railway_stations_loc ON public.railway_stations USING gist (location);
CREATE INDEX idx_railway_stations_ward ON public.railway_stations USING btree (ward);

-- ------------------------------------------------------------
-- Table: rainfall_observations
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."rainfall_observations" (
"obs_id" UUID NOT NULL DEFAULT gen_random_uuid(),
"city_id" VARCHAR(255),
"source" VARCHAR(255),
"observed_at" TIMESTAMPTZ NOT NULL,
"valid_from" TIMESTAMPTZ,
"valid_to" TIMESTAMPTZ,
"rate_mmh" DOUBLE PRECISION,
"spatial_type" VARCHAR(255),
"location" geometry(POINT, 4326),
"grid_storage_uri" TEXT,
"quality_flags" _TEXT,
"provenance" JSONB,
"station_id" VARCHAR(255),
"station_name" VARCHAR(255),
"variable" VARCHAR(255),
"value" DOUBLE PRECISION,
"unit" VARCHAR(255),
"data_source" VARCHAR(255),
"observation_type" VARCHAR(255),
"quality_flag" VARCHAR(255)
);

CREATE UNIQUE INDEX rainfall_observations_pkey ON public.rainfall_observations USING btree (obs_id);
CREATE INDEX idx_rainfall_time ON public.rainfall_observations USING btree (observed_at);
CREATE INDEX idx_rainfall_observations_location ON public.rainfall_observations USING gist (location);
CREATE INDEX idx_rainfall_city ON public.rainfall_observations USING btree (city_id, observed_at);

-- ------------------------------------------------------------
-- Table: rainfall_satellite
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."rainfall_satellite" (
"satellite_id" UUID NOT NULL DEFAULT gen_random_uuid(),
"product" VARCHAR(255) NOT NULL,
"run_type" VARCHAR(255) NOT NULL,
"version" VARCHAR(255) NOT NULL,
"timestamp" TIMESTAMPTZ NOT NULL,
"latitude" DOUBLE PRECISION NOT NULL,
"longitude" DOUBLE PRECISION NOT NULL,
"location" geometry(POINT, 4326),
"precipitation_mm_hr" DOUBLE PRECISION,
"accumulation_mm" DOUBLE PRECISION,
"quality_metric" DOUBLE PRECISION,
"raw_source_file" TEXT,
"ingested_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX rainfall_satellite_pkey ON public.rainfall_satellite USING btree (satellite_id);
CREATE INDEX idx_sat_rain_loc ON public.rainfall_satellite USING gist (location);
CREATE INDEX idx_sat_rain_prod_time ON public.rainfall_satellite USING btree (product, "timestamp");

-- ------------------------------------------------------------
-- Table: road_segments
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."road_segments" (
"segment_id" VARCHAR(255) NOT NULL,
"city_id" VARCHAR(255),
"name" VARCHAR(255),
"road_class" VARCHAR(255),
"geometry" geometry(LINESTRING, 4326) NOT NULL,
"length_m" DOUBLE PRECISION,
"speed_limit_kmh" DOUBLE PRECISION,
"osm_id" BIGINT,
"attributes" JSONB,
"is_critical_arterial" BOOLEAN  DEFAULT false
);

CREATE UNIQUE INDEX road_segments_pkey ON public.road_segments USING btree (segment_id);
CREATE INDEX idx_roads_geom ON public.road_segments USING gist (geometry);
CREATE INDEX idx_road_segments_geometry ON public.road_segments USING gist (geometry);
CREATE INDEX idx_roads_class ON public.road_segments USING btree (road_class);
CREATE INDEX idx_roads_osm_id ON public.road_segments USING btree (osm_id);

-- ------------------------------------------------------------
-- Table: satellite_rainfall_observations
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."satellite_rainfall_observations" (
"observation_id" VARCHAR(255) NOT NULL,
"satellite" VARCHAR(255) NOT NULL,
"sensor" VARCHAR(255) NOT NULL,
"product" VARCHAR(255) NOT NULL,
"product_level" VARCHAR(255) NOT NULL,
"product_description" TEXT,
"observation_time" TIMESTAMPTZ NOT NULL,
"year" INTEGER NOT NULL,
"event_name" VARCHAR(255),
"geometry" geometry(POLYGON, 4326),
"raster_width" INTEGER NOT NULL,
"raster_height" INTEGER NOT NULL,
"spatial_resolution_deg" DOUBLE PRECISION NOT NULL,
"spatial_resolution_km" DOUBLE PRECISION NOT NULL,
"min_value" DOUBLE PRECISION,
"max_value" DOUBLE PRECISION,
"mean_value" DOUBLE PRECISION,
"std_value" DOUBLE PRECISION,
"p50_value" DOUBLE PRECISION,
"p90_value" DOUBLE PRECISION,
"p99_value" DOUBLE PRECISION,
"valid_pixel_count" INTEGER NOT NULL,
"total_pixel_count" INTEGER NOT NULL,
"nodata_value" DOUBLE PRECISION NOT NULL,
"nodata_pixel_count" INTEGER NOT NULL,
"mumbai_core_max_value" DOUBLE PRECISION,
"mumbai_core_mean_value" DOUBLE PRECISION,
"unit" VARCHAR(255)  DEFAULT 'mm/hr'::character varying,
"source" VARCHAR(255)  DEFAULT 'ISRO MOSDAC'::character varying,
"source_file" TEXT NOT NULL,
"canonical_file_path" TEXT NOT NULL,
"file_hash" VARCHAR(255) NOT NULL,
"file_size_bytes" BIGINT NOT NULL,
"grid_data" JSONB,
"attributes" JSONB,
"ingestion_run_id" UUID,
"created_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX satellite_rainfall_observations_pkey ON public.satellite_rainfall_observations USING btree (observation_id);
CREATE INDEX idx_sat_rain_obs_geom ON public.satellite_rainfall_observations USING gist (geometry);
CREATE INDEX idx_sat_rain_obs_time ON public.satellite_rainfall_observations USING btree (observation_time);
CREATE INDEX idx_sat_rain_obs_prod_time ON public.satellite_rainfall_observations USING btree (product, observation_time);
CREATE INDEX idx_sat_rain_obs_prod_year ON public.satellite_rainfall_observations USING btree (product, year);
CREATE INDEX idx_sat_rain_obs_event ON public.satellite_rainfall_observations USING btree (event_name);

-- ------------------------------------------------------------
-- Table: shelters
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."shelters" (
"shelter_id" VARCHAR(255) NOT NULL,
"city_id" VARCHAR(255),
"name" VARCHAR(255) NOT NULL,
"category" VARCHAR(255),
"capacity_persons" INTEGER,
"location" geometry(POINT, 4326) NOT NULL,
"elevation_m" DOUBLE PRECISION,
"status" VARCHAR(255),
"attributes" JSONB
);

CREATE UNIQUE INDEX shelters_pkey ON public.shelters USING btree (shelter_id);
CREATE INDEX idx_shelters_location ON public.shelters USING gist (location);

-- ------------------------------------------------------------
-- Table: simulation_runs
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."simulation_runs" (
"run_id" UUID NOT NULL DEFAULT gen_random_uuid(),
"city_id" VARCHAR(255),
"mode" VARCHAR(255) NOT NULL,
"status" VARCHAR(255),
"created_at" TIMESTAMPTZ  DEFAULT now(),
"started_at" TIMESTAMPTZ,
"completed_at" TIMESTAMPTZ,
"scenario_config" JSONB NOT NULL,
"mass_balance" JSONB,
"output_manifest" JSONB,
"error" JSONB
);

CREATE UNIQUE INDEX simulation_runs_pkey ON public.simulation_runs USING btree (run_id);

-- ------------------------------------------------------------
-- Table: terrain_derivatives
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."terrain_derivatives" (
"derivative_id" UUID NOT NULL DEFAULT gen_random_uuid(),
"dem_tile_id" UUID,
"derivative_type" VARCHAR(255) NOT NULL,
"storage_path" TEXT NOT NULL,
"min_value" DOUBLE PRECISION,
"max_value" DOUBLE PRECISION,
"mean_value" DOUBLE PRECISION,
"parameters" JSONB  DEFAULT '{}'::jsonb,
"derived_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX terrain_derivatives_pkey ON public.terrain_derivatives USING btree (derivative_id);

-- ------------------------------------------------------------
-- Table: tide_observations
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."tide_observations" (
"tide_id" UUID NOT NULL DEFAULT gen_random_uuid(),
"station_name" VARCHAR(255) NOT NULL,
"latitude" DOUBLE PRECISION,
"longitude" DOUBLE PRECISION,
"location" geometry(POINT, 4326),
"timestamp" TIMESTAMPTZ NOT NULL,
"tide_height_m" DOUBLE PRECISION NOT NULL,
"datum" VARCHAR(255)  DEFAULT 'Chart Datum'::character varying,
"data_source" VARCHAR(255) NOT NULL,
"source_url" TEXT,
"quality_flag" VARCHAR(255)  DEFAULT 'verified'::character varying,
"ingested_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX tide_observations_pkey ON public.tide_observations USING btree (tide_id);
CREATE INDEX idx_tide_station_time ON public.tide_observations USING btree (station_name, "timestamp");

-- ------------------------------------------------------------
-- Table: wards
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."wards" (
"ward_id" VARCHAR(255) NOT NULL,
"city_id" VARCHAR(255) NOT NULL,
"name" VARCHAR(255),
"geometry" geometry(MULTIPOLYGON, 4326) NOT NULL,
"area_sq_km" DOUBLE PRECISION,
"population" INTEGER,
"metadata" JSONB
);

CREATE UNIQUE INDEX wards_pkey ON public.wards USING btree (ward_id);
CREATE INDEX idx_wards_geometry ON public.wards USING gist (geometry);
CREATE INDEX idx_wards_geom ON public.wards USING gist (geometry);

-- ------------------------------------------------------------
-- Table: water_bodies
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."water_bodies" (
"water_id" UUID NOT NULL DEFAULT gen_random_uuid(),
"osm_id" BIGINT,
"name" VARCHAR(255),
"feature_type" VARCHAR(255) NOT NULL,
"geometry" geometry(GEOMETRY, 4326) NOT NULL,
"area_sq_m" DOUBLE PRECISION,
"source" VARCHAR(255)  DEFAULT 'OpenStreetMap'::character varying,
"attributes" JSONB  DEFAULT '{}'::jsonb,
"ingested_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX water_bodies_pkey ON public.water_bodies USING btree (water_id);
CREATE INDEX idx_water_bodies_geom ON public.water_bodies USING gist (geometry);

-- ------------------------------------------------------------
-- Table: weather_forecasts
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."weather_forecasts" (
"forecast_id" UUID NOT NULL DEFAULT gen_random_uuid(),
"station_id" VARCHAR(255) NOT NULL,
"station_name" VARCHAR(255),
"latitude" DOUBLE PRECISION NOT NULL,
"longitude" DOUBLE PRECISION NOT NULL,
"forecast_generated_at" TIMESTAMPTZ NOT NULL,
"forecast_valid_time" TIMESTAMPTZ NOT NULL,
"lead_minutes" INTEGER NOT NULL,
"lead_hours" DOUBLE PRECISION,
"variable" VARCHAR(255) NOT NULL,
"value" DOUBLE PRECISION,
"unit" VARCHAR(255),
"model" VARCHAR(255) NOT NULL,
"quality_flag" VARCHAR(255)  DEFAULT 'forecast'::character varying,
"ingested_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX weather_forecasts_pkey ON public.weather_forecasts USING btree (forecast_id);
CREATE INDEX idx_weather_fc_station_valid ON public.weather_forecasts USING btree (station_id, forecast_valid_time);
CREATE INDEX idx_weather_fc_lead ON public.weather_forecasts USING btree (lead_minutes);
CREATE INDEX idx_weather_fc_var ON public.weather_forecasts USING btree (variable);

-- ------------------------------------------------------------
-- Table: weather_observations
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public."weather_observations" (
"obs_id" UUID NOT NULL DEFAULT gen_random_uuid(),
"station_id" VARCHAR(255) NOT NULL,
"station_name" VARCHAR(255),
"latitude" DOUBLE PRECISION NOT NULL,
"longitude" DOUBLE PRECISION NOT NULL,
"timestamp" TIMESTAMPTZ NOT NULL,
"variable" VARCHAR(255) NOT NULL,
"value" DOUBLE PRECISION,
"unit" VARCHAR(255),
"data_source" VARCHAR(255) NOT NULL,
"observation_type" VARCHAR(255)  DEFAULT 'surface_station'::character varying,
"quality_flag" VARCHAR(255)  DEFAULT 'provisional'::character varying,
"ingested_at" TIMESTAMPTZ  DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX weather_observations_pkey ON public.weather_observations USING btree (obs_id);
CREATE INDEX idx_weather_obs_station_time ON public.weather_observations USING btree (station_id, "timestamp");
CREATE INDEX idx_weather_obs_var ON public.weather_observations USING btree (variable);
