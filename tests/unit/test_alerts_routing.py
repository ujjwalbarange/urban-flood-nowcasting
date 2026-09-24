"""Tests for alerting and risk assessment."""

import pytest

from services.alerts.cap import (
    IMDSeverity,
    classify_severity_by_depth,
    classify_severity_by_rainfall,
    classify_severity_combined,
    generate_cap_xml,
)
from services.routing.dijkstra import (
    FloodAwareRouter,
    RoadEdge,
    RouteResult,
    VehicleProfile,
    Passability,
)


class TestIMDClassification:
    """Verify IMD severity classification thresholds."""

    def test_green_for_no_flooding(self):
        assert classify_severity_by_depth(0.01) == IMDSeverity.GREEN

    def test_yellow_for_shallow_flooding(self):
        assert classify_severity_by_depth(0.10) == IMDSeverity.YELLOW

    def test_orange_for_moderate_flooding(self):
        assert classify_severity_by_depth(0.20) == IMDSeverity.ORANGE

    def test_red_for_deep_flooding(self):
        assert classify_severity_by_depth(0.50) == IMDSeverity.RED

    def test_green_for_light_rain(self):
        assert classify_severity_by_rainfall(10.0) == IMDSeverity.GREEN

    def test_red_for_extreme_rain(self):
        assert classify_severity_by_rainfall(200.0) == IMDSeverity.RED

    def test_combined_takes_maximum(self):
        """Combined severity should be the higher of depth and rainfall."""
        result = classify_severity_combined(
            max_depth_m=0.01,       # GREEN by depth
            rainfall_mm_day=100.0,  # ORANGE by rainfall
        )
        assert result == IMDSeverity.ORANGE


class TestCAPGeneration:
    """Verify CAP v1.2 XML generation."""

    def test_generates_valid_xml(self):
        xml = generate_cap_xml(
            city_name="Mumbai",
            severity=IMDSeverity.ORANGE,
            max_depth_m=0.25,
            affected_wards=["A", "B"],
        )
        assert '<?xml version="1.0"' in xml
        assert "urn:oasis:names:tc:emergency:cap:1.2" in xml
        assert "Mumbai" in xml
        assert "Severe" in xml  # ORANGE → Severe in CAP
        assert "0.250" in xml  # max depth parameter

    def test_contains_required_cap_elements(self):
        xml = generate_cap_xml(severity=IMDSeverity.RED)
        for element in ["identifier", "sender", "sent", "status", "msgType",
                       "scope", "category", "event", "urgency", "severity",
                       "certainty", "headline", "description"]:
            assert f"<{element}>" in xml, f"Missing required CAP element: {element}"


class TestFloodAwareRouting:
    """Verify flood-aware Dijkstra routing."""

    def _build_simple_graph(self):
        """Build a simple 4-node graph: A→B→C→D (with flood on B→C)."""
        router = FloodAwareRouter(vehicle=VehicleProfile.CAR)
        edges = [
            RoadEdge("e1", "A", "B", 1000.0, 50.0, flood_depth_m=0.0),
            RoadEdge("e2", "B", "C", 1000.0, 50.0, flood_depth_m=0.40),  # Difficult
            RoadEdge("e3", "C", "D", 1000.0, 50.0, flood_depth_m=0.0),
            # Alternate route: A→E→D (longer but dry)
            RoadEdge("e4", "A", "E", 2000.0, 50.0, flood_depth_m=0.0),
            RoadEdge("e5", "E", "D", 2000.0, 50.0, flood_depth_m=0.0),
        ]
        router.build_graph(edges)
        return router

    def test_finds_route(self):
        router = self._build_simple_graph()
        result = router.find_route("A", "D")
        assert result.found is True
        assert result.total_distance_m > 0

    def test_avoids_impassable_road(self):
        """Router should prefer longer dry route over shorter flooded one."""
        router = FloodAwareRouter(vehicle=VehicleProfile.CAR)
        edges = [
            RoadEdge("e1", "A", "B", 100.0, 50.0, flood_depth_m=0.60),  # Impassable
            RoadEdge("e2", "A", "C", 500.0, 50.0, flood_depth_m=0.0),   # Dry, longer
            RoadEdge("e3", "C", "B", 500.0, 50.0, flood_depth_m=0.0),   # Dry
        ]
        router.build_graph(edges)
        result = router.find_route("A", "B")
        assert result.found is True
        # Should take A→C→B (1000m) instead of A→B (100m, impassable)
        assert result.total_distance_m > 500

    def test_no_route_when_all_impassable(self):
        router = FloodAwareRouter(vehicle=VehicleProfile.CAR)
        edges = [
            RoadEdge("e1", "A", "B", 1000.0, 50.0, flood_depth_m=0.80),  # Impassable
        ]
        router.build_graph(edges)
        result = router.find_route("A", "B")
        assert result.found is False

    def test_nearest_shelter(self):
        router = self._build_simple_graph()
        result = router.find_nearest_shelter("A", ["C", "D"])
        assert result is not None
        assert result.found is True
        assert result.destination in ["C", "D"]
