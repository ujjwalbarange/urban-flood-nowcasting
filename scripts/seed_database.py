"""Seed Aiven PostGIS database with all Mumbai geospatial datasets.

Loads:
 - City config + boundary
 - 24 ward polygons
 - 202 historical flood events (2016-2025)
 - 10 flood hotspots
 - 14 drainage nodes + 8 links + 11 outfalls
 - 10 shelters
 - 15 roads
 - Data source registry

Run:  python scripts/seed_database.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 on Windows console
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from sqlalchemy import text
from services.database.connection import engine, Base
from services.database.models import (
    City, Ward, HistoricalFloodEvent, FloodHotspot,
    DrainageNodeDB, DrainageLinkDB, Shelter, RoadSegment,
    DataSource, CriticalInfrastructure, PumpingStation,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

DATA_PKG = PROJECT_ROOT / "mumbai_flood_data_package"
FLOOD_EVENTS_FILE = PROJECT_ROOT / "mumbai_urban_flood_2016_2025 (1).geojson"


def _load_geojson(path: Path) -> dict:
    if not path.exists():
        print(f"  [SKIP] {path.name} not found")
        return {"type": "FeatureCollection", "features": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _wkt_point(lon: float, lat: float) -> str:
    return f"SRID=4326;POINT({lon} {lat})"


def _wkt_from_geojson_geometry(geom: dict) -> str:
    """Convert GeoJSON geometry dict to WKT with SRID."""
    gtype = geom["type"]
    coords = geom["coordinates"]

    if gtype == "Point":
        return f"SRID=4326;POINT({coords[0]} {coords[1]})"

    elif gtype == "LineString":
        pts = ", ".join(f"{c[0]} {c[1]}" for c in coords)
        return f"SRID=4326;LINESTRING({pts})"

    elif gtype == "Polygon":
        rings = []
        for ring in coords:
            pts = ", ".join(f"{c[0]} {c[1]}" for c in ring)
            rings.append(f"({pts})")
        return f"SRID=4326;POLYGON({', '.join(rings)})"

    elif gtype == "MultiPolygon":
        polys = []
        for polygon in coords:
            rings = []
            for ring in polygon:
                pts = ", ".join(f"{c[0]} {c[1]}" for c in ring)
                rings.append(f"({pts})")
            polys.append(f"({', '.join(rings)})")
        return f"SRID=4326;MULTIPOLYGON({', '.join(polys)})"

    else:
        raise ValueError(f"Unsupported geometry type: {gtype}")


async def seed():
    print("=" * 60)
    print("MUFNS Database Seeder -- PostGIS")
    print("=" * 60)

    # 1. Create all tables
    print("\n[1/9] Creating tables...")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await conn.run_sync(Base.metadata.create_all)
    print("  [OK] All tables created")

    async with async_session() as session:
        # 2. Seed City
        print("\n[2/9] Seeding city...")
        city_config = _load_geojson(DATA_PKG / "01_city" / "config.json")
        existing = await session.get(City, "mumbai")
        if not existing:
            boundary_gj = _load_geojson(DATA_PKG / "01_city" / "mumbai_boundary.geojson")
            bbox_wkt = None
            if boundary_gj["features"]:
                bbox_wkt = _wkt_from_geojson_geometry(boundary_gj["features"][0]["geometry"])

            city = City(
                city_id="mumbai",
                name="Mumbai (Greater Mumbai)",
                state="Maharashtra",
                country="IN",
                crs_epsg=4326,
                cell_size_m=30.0,
                bbox=bbox_wkt,
                timezone="Asia/Kolkata",
                config=city_config if isinstance(city_config, dict) else {},
            )
            session.add(city)
            await session.flush()
            print("  [OK] City 'mumbai' created")
        else:
            print("  -> City 'mumbai' already exists")

        # 3. Seed Wards
        print("\n[3/9] Seeding wards...")
        wards_gj = _load_geojson(DATA_PKG / "01_city" / "wards.geojson")
        ward_count = 0
        for feat in wards_gj.get("features", []):
            props = feat["properties"]
            wid = props.get("ward_id", "")
            existing_ward = await session.get(Ward, wid)
            if existing_ward:
                continue

            # Convert Polygon to MultiPolygon for the model
            geom = feat["geometry"]
            if geom["type"] == "Polygon":
                geom = {"type": "MultiPolygon", "coordinates": [geom["coordinates"]]}

            ward = Ward(
                ward_id=wid,
                city_id="mumbai",
                name=props.get("ward_name", ""),
                geometry=_wkt_from_geojson_geometry(geom),
                area_sq_km=props.get("area_sq_km"),
                population=props.get("population_2011"),
                metadata_={
                    "zone": props.get("zone"),
                    "headquarters": props.get("headquarters"),
                    "population_density_per_sq_km": props.get("population_density_per_sq_km"),
                    "source": props.get("source"),
                },
            )
            session.add(ward)
            ward_count += 1
        await session.flush()
        print(f"  [OK] {ward_count} wards seeded")

        # 4. Seed Historical Flood Events (202 records)
        print("\n[4/9] Seeding historical flood events...")
        flood_count = 0
        if FLOOD_EVENTS_FILE.exists():
            flood_gj = _load_geojson(FLOOD_EVENTS_FILE)
            for feat in flood_gj.get("features", []):
                props = feat["properties"]
                eid = props.get("event_id", "")
                if not eid:
                    continue
                # Make event_id unique per feature by appending coords
                lat = props.get("latitude", 0)
                lon = props.get("longitude", 0)
                unique_id = f"{eid}_{lat}_{lon}"

                existing_evt = await session.get(HistoricalFloodEvent, unique_id)
                if existing_evt:
                    continue

                date_str = props.get("date", "2020-01-01")
                try:
                    date_obj = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    date_obj = datetime(2020, 1, 1, tzinfo=timezone.utc)

                evt = HistoricalFloodEvent(
                    event_id=unique_id,
                    city_id="mumbai",
                    date=date_obj,
                    year=props.get("year"),
                    ward=props.get("ward"),
                    locality=props.get("locality"),
                    location=_wkt_point(lon, lat),
                    elevation_m=props.get("elevation_m"),
                    slope_degree=props.get("slope_degree"),
                    distance_to_drain_m=props.get("distance_to_drain_m"),
                    distance_to_waterbody_m=props.get("distance_to_waterbody_m"),
                    rainfall_1h_mm=props.get("rainfall_1h_mm"),
                    rainfall_3h_mm=props.get("rainfall_3h_mm"),
                    rainfall_6h_mm=props.get("rainfall_6h_mm"),
                    rainfall_12h_mm=props.get("rainfall_12h_mm"),
                    rainfall_24h_mm=props.get("rainfall_24h_mm"),
                    rainfall_48h_mm=props.get("rainfall_48h_mm"),
                    rainfall_72h_mm=props.get("rainfall_72h_mm"),
                    rainfall_intensity_mm_h=props.get("rainfall_intensity_mm_h"),
                    rainfall_anomaly=props.get("rainfall_anomaly"),
                    antecedent_rainfall_3day_mm=props.get("antecedent_rainfall_3day_mm"),
                    antecedent_rainfall_7day_mm=props.get("antecedent_rainfall_7day_mm"),
                    soil_moisture=props.get("soil_moisture"),
                    soil_type=props.get("soil_type"),
                    infiltration_rate=props.get("infiltration_rate"),
                    groundwater_level_m=props.get("groundwater_level_m"),
                    drain_water_level_m=props.get("drain_water_level_m"),
                    built_up_percentage=props.get("built_up_percentage"),
                    impervious_surface_percentage=props.get("impervious_surface_percentage"),
                    vegetation_percentage=props.get("vegetation_percentage"),
                    population_density=props.get("population_density"),
                    drainage_capacity=props.get("drainage_capacity"),
                    ndvi=props.get("NDVI"),
                    ndwi=props.get("NDWI"),
                    ndbi=props.get("NDBI"),
                    flooded_area_km2=props.get("flooded_area_km2"),
                    flood_occurred=bool(props.get("flood_occurred", True)),
                    flood_depth_cm=props.get("flood_depth_cm"),
                    flood_duration_hours=props.get("flood_duration_hours"),
                    waterlogging_duration_hours=props.get("waterlogging_duration_hours"),
                    flood_severity=props.get("flood_severity"),
                    people_affected=int(props["people_affected"]) if props.get("people_affected") else None,
                    houses_affected=int(props["houses_affected"]) if props.get("houses_affected") else None,
                    roads_affected=int(props["roads_affected"]) if props.get("roads_affected") else None,
                    economic_loss=props.get("economic_loss"),
                    rainfall_intensity_index=props.get("rainfall_intensity_index"),
                    drainage_stress_index=props.get("drainage_stress_index"),
                    imperviousness_index=props.get("imperviousness_index"),
                    data_source=props.get("data_source"),
                    source_url=props.get("source_url"),
                    data_type=props.get("data_type", "observed"),
                )
                session.add(evt)
                flood_count += 1
            await session.flush()
        print(f"  [OK] {flood_count} historical flood events seeded")

        # 5. Seed Flood Hotspots
        print("\n[5/9] Seeding flood hotspots...")
        hotspots_gj = _load_geojson(DATA_PKG / "08_flood_observations" / "flood_points.geojson")
        hs_count = 0
        for feat in hotspots_gj.get("features", []):
            props = feat["properties"]
            hid = props.get("spot_id") or props.get("id") or (props.get("location_name") or props.get("name", "")).replace(" ", "_").lower()[:60]
            if not hid:
                continue
            existing_hs = await session.get(FloodHotspot, str(hid))
            if existing_hs:
                continue
            coords = feat["geometry"]["coordinates"]
            name = props.get("location_name") or props.get("name", "Unknown")
            depth = props.get("maximum_recorded_depth_m") or props.get("typical_water_depth_m") or props.get("peak_depth_m")
            hs = FloodHotspot(
                hotspot_id=str(hid),
                city_id="mumbai",
                name=name,
                ward=props.get("ward", ""),
                location=_wkt_point(coords[0], coords[1]),
                severity=props.get("traffic_impact", "high")[:32] if "Severe" in str(props.get("traffic_impact", "")) else "moderate",
                historical_max_depth_m=float(depth) if depth is not None else None,
                recurrence=props.get("drainage_basin", "annual"),
                data_source=props.get("source", "MCGM/BMC chronic spots inventory"),
                attributes=props,
            )
            session.add(hs)
            hs_count += 1
        await session.commit()
        print(f"  [OK] {hs_count} flood hotspots seeded")

        # 6. Seed Drainage Nodes + Outfalls + Pumping Stations
        print("\n[6/9] Seeding drainage network & pumping stations...")
        known_nodes = set()
        dn_count = 0
        ps_count = 0

        # 6a. Main nodes
        nodes_gj = _load_geojson(DATA_PKG / "06_drainage" / "nodes.geojson")
        for feat in nodes_gj.get("features", []):
            props = feat["properties"]
            nid = str(props.get("node_id") or props.get("id", ""))
            if not nid:
                continue
            known_nodes.add(nid)
            coords = feat["geometry"]["coordinates"]
            existing_dn = await session.get(DrainageNodeDB, nid)
            if not existing_dn:
                dn = DrainageNodeDB(
                    node_id=nid,
                    city_id="mumbai",
                    node_type=props.get("type") or props.get("node_type", "junction"),
                    geometry=_wkt_point(coords[0], coords[1]),
                    invert_elevation_m=props.get("invert_elevation_m_msl") or props.get("invert_elevation_m"),
                    ground_elevation_m=props.get("ground_elevation_m_msl") or props.get("ground_elevation_m"),
                    data_quality=props.get("data_quality", "high_surveyed"),
                    attributes=props,
                )
                session.add(dn)
                dn_count += 1

            # Seed pumping station if applicable
            if "pumping_station" in str(props.get("type", "")).lower() or "Pumping Station" in str(props.get("name", "")):
                existing_ps = await session.get(PumpingStation, nid)
                if not existing_ps:
                    cap_m3s = props.get("pump_capacity_m3_per_sec", 0.0) or 0.0
                    ps = PumpingStation(
                        pump_id=nid,
                        city_id="mumbai",
                        name=props.get("name", nid),
                        ward=props.get("ward", ""),
                        location=_wkt_point(coords[0], coords[1]),
                        num_pumps=props.get("num_pumps", 4),
                        rated_capacity_mld=float(cap_m3s) * 86.4,  # m3/s to MLD
                        current_status=props.get("status", "operational"),
                        operational_capacity_pct=100.0,
                        data_source="BRIMSTOWAD Master Plan / BMC",
                        attributes=props,
                    )
                    session.add(ps)
                    ps_count += 1

        # 6b. Outfalls as drainage nodes
        outfalls_gj = _load_geojson(DATA_PKG / "06_drainage" / "outfalls.geojson")
        for feat in outfalls_gj.get("features", []):
            props = feat["properties"]
            oid = str(props.get("outfall_id") or props.get("id", ""))
            if not oid:
                continue
            known_nodes.add(oid)
            coords = feat["geometry"]["coordinates"]
            existing_of = await session.get(DrainageNodeDB, oid)
            if not existing_of:
                of_node = DrainageNodeDB(
                    node_id=oid,
                    city_id="mumbai",
                    node_type="outfall",
                    geometry=_wkt_point(coords[0], coords[1]),
                    invert_elevation_m=props.get("invert_elevation_m_msl"),
                    ground_elevation_m=props.get("critical_tide_level_m_cd"),
                    data_quality="high_surveyed",
                    attributes=props,
                )
                session.add(of_node)
                dn_count += 1

        # Pre-scan links to create any missing endpoint nodes
        links_gj = _load_geojson(DATA_PKG / "06_drainage" / "links.geojson")
        for feat in links_gj.get("features", []):
            props = feat["properties"]
            coords = feat["geometry"]["coordinates"]
            fn = props.get("from_node")
            tn = props.get("to_node")
            if fn and fn not in known_nodes:
                existing_fn = await session.get(DrainageNodeDB, str(fn))
                if not existing_fn:
                    first_pt = coords[0] if coords else [72.85, 19.05]
                    session.add(DrainageNodeDB(
                        node_id=str(fn),
                        city_id="mumbai",
                        node_type="junction",
                        geometry=_wkt_point(first_pt[0], first_pt[1]),
                        data_quality="derived_topology",
                        attributes={"auto_created": True},
                    ))
                    known_nodes.add(str(fn))
                    dn_count += 1
            if tn and tn not in known_nodes:
                existing_tn = await session.get(DrainageNodeDB, str(tn))
                if not existing_tn:
                    last_pt = coords[-1] if coords else [72.85, 19.05]
                    session.add(DrainageNodeDB(
                        node_id=str(tn),
                        city_id="mumbai",
                        node_type="outfall" if "outfall" in str(tn).lower() else "junction",
                        geometry=_wkt_point(last_pt[0], last_pt[1]),
                        data_quality="derived_topology",
                        attributes={"auto_created": True},
                    ))
                    known_nodes.add(str(tn))
                    dn_count += 1

        await session.flush()

        # 6c. Drainage links
        dl_count = 0
        for feat in links_gj.get("features", []):
            props = feat["properties"]
            lid = props.get("link_id") or props.get("id", "")
            if not lid:
                continue
            existing_dl = await session.get(DrainageLinkDB, str(lid))
            if existing_dl:
                continue
            dl = DrainageLinkDB(
                link_id=str(lid),
                city_id="mumbai",
                from_node=props.get("from_node"),
                to_node=props.get("to_node"),
                link_type=props.get("channel_type") or props.get("link_type", "channel"),
                geometry=_wkt_from_geojson_geometry(feat["geometry"]),
                diameter_m=props.get("width_m") or props.get("diameter_m"),
                length_m=props.get("length_m"),
                manning_n=props.get("manning_n"),
                data_quality="surveyed_trunk",
                attributes=props,
            )
            session.add(dl)
            dl_count += 1

        await session.commit()
        print(f"  [OK] {dn_count} nodes/outfalls, {dl_count} links, {ps_count} pumping stations seeded")

        # 7. Seed Shelters
        print("\n[7/9] Seeding shelters...")
        shelters_gj = _load_geojson(DATA_PKG / "10_shelters" / "shelters.geojson")
        sh_count = 0
        for feat in shelters_gj.get("features", []):
            props = feat["properties"]
            sid = props.get("shelter_id") or props.get("id") or props.get("name", "").replace(" ", "_").lower()[:60]
            if not sid:
                continue
            existing_sh = await session.get(Shelter, str(sid))
            if existing_sh:
                continue
            coords = feat["geometry"]["coordinates"]
            sh = Shelter(
                shelter_id=str(sid),
                city_id="mumbai",
                name=props.get("name", "Emergency Shelter"),
                category=props.get("category", "relief_center"),
                capacity_persons=props.get("capacity_persons") or props.get("capacity"),
                location=_wkt_point(coords[0], coords[1]),
                elevation_m=props.get("elevation_m"),
                status=props.get("status", "operational"),
                attributes=props,
            )
            session.add(sh)
            sh_count += 1
        await session.flush()
        print(f"  [OK] {sh_count} shelters seeded")

        # 8. Seed Roads
        print("\n[8/9] Seeding roads...")
        roads_gj = _load_geojson(DATA_PKG / "04_roads" / "roads.geojson")
        rd_count = 0
        for i, feat in enumerate(roads_gj.get("features", [])):
            props = feat["properties"]
            rid = props.get("segment_id") or props.get("id") or f"road_{i}"
            existing_rd = await session.get(RoadSegment, str(rid))
            if existing_rd:
                continue
            rd = RoadSegment(
                segment_id=str(rid),
                city_id="mumbai",
                name=props.get("name", ""),
                road_class=props.get("road_class") or props.get("highway", ""),
                geometry=_wkt_from_geojson_geometry(feat["geometry"]),
                length_m=props.get("length_m"),
                speed_limit_kmh=props.get("speed_limit_kmh"),
                osm_id=props.get("osm_id"),
                attributes=props,
            )
            session.add(rd)
            rd_count += 1
        await session.flush()
        print(f"  [OK] {rd_count} road segments seeded")

        # 9. Seed Critical Infrastructure
        print("\n[9/10] Seeding critical infrastructure (hospitals, schools, government)...")
        bldgs_gj = _load_geojson(DATA_PKG / "05_buildings" / "buildings.geojson")
        ci_count = 0
        for feat in bldgs_gj.get("features", []):
            props = feat["properties"]
            cid = str(props.get("osm_id") or props.get("id") or f"ci_{ci_count}")
            existing_ci = await session.get(CriticalInfrastructure, cid)
            if existing_ci:
                continue
            coords = feat["geometry"]["coordinates"]
            # calculate polygon centroid
            pts = coords[0] if coords and isinstance(coords[0], list) and isinstance(coords[0][0], list) else (coords if coords and isinstance(coords[0], list) else [])
            if pts:
                clon = sum(p[0] for p in pts) / len(pts)
                clat = sum(p[1] for p in pts) / len(pts)
            else:
                clon, clat = 72.85, 19.05

            ci = CriticalInfrastructure(
                infra_id=cid,
                city_id="mumbai",
                name=props.get("name", "Civic Building"),
                category=props.get("category") or props.get("building_type", "civic"),
                ward=props.get("ward", ""),
                location=_wkt_point(clon, clat),
                elevation_m=props.get("elevation_m"),
                flood_vulnerable=True if "hospital" in str(props.get("category", "")).lower() or "emergency" in str(props.get("category", "")).lower() else False,
                data_source=props.get("source", "OpenStreetMap contributors / BMC"),
                attributes=props,
            )
            session.add(ci)
            ci_count += 1
        await session.flush()
        print(f"  [OK] {ci_count} critical infrastructure assets seeded")

        # 10. Seed Data Sources registry
        print("\n[10/10] Seeding data source registry...")
        sources = [
            DataSource(
                source_id="open_meteo",
                provider_name="Open-Meteo",
                provider_type="api",
                description="Free weather API -- current conditions + 7-day hourly forecast + historical ERA5",
                url="https://api.open-meteo.com",
                license="CC-BY 4.0",
                spatial_resolution="~11km (ERA5) / ~1km (ICON-EU)",
                temporal_resolution="hourly",
                status="available",
            ),
            DataSource(
                source_id="nasa_imerg",
                provider_name="NASA GPM IMERG",
                provider_type="satellite",
                description="Integrated Multi-satellitE Retrievals for GPM -- calibrated precipitation estimates",
                url="https://disc.gsfc.nasa.gov",
                license="NASA Open Data",
                spatial_resolution="0.1 deg (~10km)",
                temporal_resolution="30-minute",
                status="available",
            ),
            DataSource(
                source_id="copernicus_dem",
                provider_name="Copernicus GLO-30 DEM via OpenTopography",
                provider_type="file",
                description="30m Digital Elevation Model -- Copernicus satellite mission",
                url="https://portal.opentopography.org",
                license="Copernicus Open Access",
                spatial_resolution="30m",
                temporal_resolution="static",
                status="available",
            ),
            DataSource(
                source_id="bmc_wards",
                provider_name="BMC / MCGM Ward Boundaries",
                provider_type="file",
                description="24 administrative ward boundaries -- Brihanmumbai Municipal Corporation",
                url="https://portal.mcgm.gov.in",
                license="Government of India Open Data",
                spatial_resolution="ward-level",
                temporal_resolution="static",
                status="available",
            ),
            DataSource(
                source_id="mumbai_flood_observations",
                provider_name="Mumbai Flood Observations 2016-2025",
                provider_type="file",
                description="202 historical flood event records with rainfall, depth, impact data",
                url="https://mausam.imd.gov.in/mumbai/",
                license="IMD / MCGM Disaster Management",
                spatial_resolution="point-level",
                temporal_resolution="event-based",
                status="available",
            ),
            DataSource(
                source_id="mosdac",
                provider_name="MOSDAC / ISRO",
                provider_type="api",
                description="Meteorological and Oceanographic Satellite Data Archival Centre",
                url="https://mosdac.gov.in",
                status="unavailable",
            ),
            DataSource(
                source_id="sentinel_1_sar",
                provider_name="Sentinel-1 SAR",
                provider_type="satellite",
                description="C-band SAR imagery for flood extent detection -- ESA Copernicus",
                url="https://scihub.copernicus.eu",
                license="Copernicus Open Access",
                spatial_resolution="10m",
                temporal_resolution="6-12 day revisit",
                status="available",
            ),
        ]
        for src in sources:
            existing_src = await session.get(DataSource, src.source_id)
            if not existing_src:
                session.add(src)
        await session.flush()
        print(f"  [OK] {len(sources)} data sources registered")

        await session.commit()

    # Verify
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    async with engine.connect() as conn:
        tables = [
            "cities", "wards", "historical_flood_events", "flood_hotspots",
            "drainage_nodes", "drainage_links", "pumping_stations",
            "critical_infrastructure", "shelters", "road_segments",
            "data_sources",
        ]
        for table in tables:
            try:
                r = await conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = r.scalar()
                print(f"  {table}: {count} rows")
            except Exception as e:
                print(f"  {table}: ERROR -- {str(e)[:80]}")

        # Test spatial query
        print("\n  [Spatial Query Test]")
        r = await conn.execute(text(
            "SELECT ward, COUNT(*) FROM historical_flood_events GROUP BY ward ORDER BY COUNT(*) DESC LIMIT 5"
        ))
        for row in r.fetchall():
            print(f"    {row[0]}: {row[1]} events")

    await engine.dispose()
    print("\n[OK] Database seeding complete!")


if __name__ == "__main__":
    asyncio.run(seed())
