"""Unit and integration tests for Phase 4:
- Dynamic subarea hierarchy and topological neighbor discovery
- Spatially bounded 3D terrain heightfield extraction (Copernicus DEM)
- Spatially bounded 3D flood depth & water-surface elevation extrusion
- Real road network graph (14,563 OSM segments) and flood-impeded evacuation routing
- Candidate shelter/hospital destination ranking
- Zero mock policy & mandatory non-guaranteed safety disclaimer compliance
- Performance lag fix: synthetic drainage lines-only endpoint filter
"""

import pytest
from fastapi.testclient import TestClient

from services.api.main import app
from services.spatial.hierarchy import SubareaHierarchyEngine, get_hierarchy_engine
from services.terrain.subarea_3d import extract_subarea_terrain_3d
from services.flood.subarea_flood3d import extract_subarea_flood_3d
from services.routing.evacuation_engine import MumbaiEvacuationRoutingEngine, get_routing_engine

client = TestClient(app)


class TestSubareaHierarchy:
    """Verify dynamic discovery and topological neighbor calculation."""

    def test_dynamic_subarea_discovery(self):
        engine = get_hierarchy_engine()
        subareas = engine.list_subareas()
        # Verify genuine subarea count from data/cities/mumbai/subareas.geojson
        assert len(subareas) == 80
        for sa in subareas:
            assert "subarea_id" in sa
            assert "name" in sa
            assert "parent_ward_id" in sa
            assert "area_sq_km" in sa
            assert sa["area_sq_km"] > 0.0
            assert "centroid" in sa
            assert len(sa["centroid"]) == 2
            assert "bounds" in sa
            b = sa["bounds"]
            assert b["min_lon"] < b["max_lon"]
            assert b["min_lat"] < b["max_lat"]

    def test_topological_neighbor_computation(self):
        engine = get_hierarchy_engine()
        # Test subarea A_SA1 (South Mumbai)
        sub = engine.get_subarea("A_SA1")
        assert sub is not None
        assert sub["subarea_id"] == "A_SA1"
        neighbors = engine.get_neighbors("A_SA1")
        assert len(neighbors) > 0
        for nb in neighbors:
            assert nb["neighbor_subarea_id"] != "A_SA1"
            assert nb["shared_boundary_length_meters"] >= 0.0
            assert "parent_ward_id" in nb

    def test_hierarchy_validation_report(self):
        engine = get_hierarchy_engine()
        report = engine.validate_hierarchy()
        assert report["is_valid"] is True
        assert report["total_subareas"] == 80
        assert report["total_parent_wards"] == 24
        assert report["invalid_geometry_count"] == 0


class TestSubarea3DTerrain:
    """Verify spatially bounded 3D terrain extraction from Copernicus GLO-30 DEM."""

    def test_bounded_terrain_heightfield_extraction(self):
        terrain = extract_subarea_terrain_3d("A_SA1", target_grid_dim=64)
        assert terrain is not None
        assert terrain["subarea_id"] == "A_SA1"
        assert terrain["dimensions"]["rows"] == 64
        assert terrain["dimensions"]["cols"] == 64
        assert "EGM96" in terrain["dimensions"]["vertical_datum"]
        assert "Copernicus" in terrain["dimensions"]["data_source"]

        elevations = terrain["elevations"]
        assert len(elevations) == 64
        assert len(elevations[0]) == 64
        assert terrain["min_elevation_m"] <= terrain["mean_elevation_m"] <= terrain["max_elevation_m"]

        # Check subarea binary inclusion mask
        mask = terrain["subarea_mask"]
        assert len(mask) == 64
        assert len(mask[0]) == 64
        # Some cells must be True (inside subarea) and some False (neighboring context)
        true_count = sum(row.count(True) for row in mask)
        assert true_count > 0
        assert true_count < 64 * 64

    def test_invalid_subarea_handling(self):
        terrain = extract_subarea_terrain_3d("NONEXISTENT_SA999")
        assert terrain is None


class TestSubareaFlood3D:
    """Verify local 3D water surface and depth extrusion."""

    def test_flood_3d_extraction_schema(self):
        flood = extract_subarea_flood_3d("A_SA1", target_grid_dim=64)
        assert isinstance(flood, dict)
        assert "available" in flood
        assert flood["subarea_id"] == "A_SA1"

        if flood["available"]:
            assert flood["status"] in ("ok", "completed")
            assert "run_id" in flood
            assert flood["depth_units"] == "meters"
            assert "EGM96" in flood["vertical_datum"]
            depths = flood["depths"]
            assert len(depths) == 64
            assert len(depths[0]) == 64

            # Verify dry-cell threshold: no depth between 0.0 and 0.01m exists
            for row in depths:
                for d in row:
                    assert d == 0.0 or d >= 0.01, f"Found depth {d} below dry threshold"

            water_surfaces = flood["water_surface_elevations"]
            assert len(water_surfaces) == 64


class TestRoadGraphAndEvacuationRouting:
    """Verify graph build on 14,563 OSM road segments and flood-impeded Dijkstra pathfinding."""

    def test_road_network_graph_properties(self):
        engine = get_routing_engine()
        assert engine.graph is not None
        assert engine.graph.number_of_nodes() > 10000
        assert engine.graph.number_of_edges() >= 14563
        assert engine._kdtree is not None

    def test_candidate_destinations_ranking(self):
        engine = get_routing_engine()
        dests = engine.get_eligible_destinations("A_SA1", limit=5)
        assert len(dests) > 0
        first = dests[0]
        assert "destination_id" in first
        assert "name" in first
        assert "category" in first
        assert "distance_km" in first
        assert first["distance_km"] > 0.0
        # Verify sorted by distance ascending
        for i in range(len(dests) - 1):
            assert dests[i]["distance_km"] <= dests[i + 1]["distance_km"]

    def test_evacuation_route_calculation_and_disclaimer(self):
        engine = get_routing_engine()
        hier = get_hierarchy_engine()
        subarea = hier.get_subarea("A_SA1")
        assert subarea is not None

        dests = engine.get_eligible_destinations("A_SA1", limit=1)
        assert len(dests) > 0
        dest = dests[0]

        route = engine.compute_evacuation_route(
            origin_lon=subarea["centroid"][0],
            origin_lat=subarea["centroid"][1],
            dest_lon=dest["coordinates"][0],
            dest_lat=dest["coordinates"][1],
            destination_name=dest["name"],
            vehicle_type="standard_car",
        )
        assert route["route_found"] is True
        assert route["total_distance_km"] > 0.0
        assert route["estimated_travel_time_min"] > 0.0
        assert "CLEAR" in route["passability_verdict"] or "CAUTION" in route["passability_verdict"] or "HAZARDOUS" in route["passability_verdict"]
        assert len(route["geometry"]["coordinates"]) > 5

        # PERMANENT REQUIREMENT: Prominent non-guaranteed safety disclaimer
        disclaimer = route.get("disclaimer", "")
        assert "Not guaranteed safe" in disclaimer
        assert "emergency service" in disclaimer


class TestSubareaFastAPIEndpoints:
    """Verify FastAPI REST API endpoints for Phase 4."""

    def test_endpoint_get_subareas(self):
        res = client.get("/api/v1/subareas")
        assert res.status_code == 200
        data = res.json()
        assert data["total"] == 80
        assert len(data["subareas"]) == 80

    def test_endpoint_get_subarea_detail(self):
        res = client.get("/api/v1/subareas/A_SA1")
        assert res.status_code == 200
        data = res.json()
        assert data["subarea_id"] == "A_SA1"
        assert len(data["neighbors"]) > 0

    def test_endpoint_get_terrain3d(self):
        res = client.get("/api/v1/subareas/A_SA1/terrain3d")
        assert res.status_code == 200
        data = res.json()
        assert data["dimensions"]["rows"] == 64
        assert len(data["elevations"]) == 64

    def test_endpoint_get_flood3d(self):
        res = client.get("/api/v1/subareas/A_SA1/flood3d")
        assert res.status_code == 200
        data = res.json()
        assert data["subarea_id"] == "A_SA1"

    def test_endpoint_get_destinations(self):
        res = client.get("/api/v1/subareas/A_SA1/destinations")
        assert res.status_code == 200
        data = res.json()
        assert "destinations" in data
        assert len(data["destinations"]) > 0

    def test_endpoint_post_evacuation_route(self):
        res_dests = client.get("/api/v1/subareas/A_SA1/destinations")
        dest_id = res_dests.json()["destinations"][0]["destination_id"]

        res = client.post(
            "/api/v1/subareas/A_SA1/evacuation-route",
            json={"destination_id": dest_id, "vehicle_type": "standard_car"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["route_found"] is True
        assert data["total_distance_km"] > 0.0
        assert "disclaimer" in data

    def test_drainage_synthetic_lines_only_lag_fix(self):
        """Verify performance lag fix: lines_only=true filters out Point markers."""
        res = client.get("/api/v1/drainage/synthetic?lines_only=true")
        assert res.status_code == 200
        data = res.json()
        features = data.get("features", [])
        assert len(features) > 0
        for f in features:
            geom_type = f.get("geometry", {}).get("type")
            assert geom_type in ("LineString", "MultiLineString"), f"Unexpected geometry {geom_type} in lines_only mode"
