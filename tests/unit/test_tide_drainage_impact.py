"""Unit tests for Tide, Drainage, and Impact modules (Phase 2E)."""

import pytest
from httpx import AsyncClient, ASGITransport

from services.api.main import app
from services.coastal.tide_service import (
    TideService,
    TideScenario,
    MUMBAI_MHWS_M_CD,
    MUMBAI_DATUM_OFFSET_M,
)
from services.impact.assessment import compute_flood_impact, FloodImpact


@pytest.mark.asyncio
async def test_tide_service_schedule_generation():
    """Verify continuous boundary schedule generation for rainfall_high_tide."""
    service = TideService()
    sched = await service.build_tide_schedule(TideScenario.RAINFALL_HIGH_TIDE, duration_hours=6.0)

    assert sched is not None
    assert sched.scenario == TideScenario.RAINFALL_HIGH_TIDE
    assert sched.datum == "MSL"
    assert sched.peak_tide_m_cd == MUMBAI_MHWS_M_CD
    assert round(sched.peak_tide_m_msl, 2) == round(MUMBAI_MHWS_M_CD - MUMBAI_DATUM_OFFSET_M, 2)
    assert len(sched.schedule) > 10  # 15-min intervals across 6h

    # Test rainfall_only free drainage boundary
    free_sched = await service.build_tide_schedule(TideScenario.RAINFALL_ONLY, duration_hours=3.0)
    assert free_sched.peak_tide_m_msl == -2.0


@pytest.mark.asyncio
async def test_tide_api_endpoints():
    """Verify /api/v1/tide endpoints return valid JSON and schema."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Current tide
        r = await client.get("/api/v1/tide/current")
        assert r.status_code == 200
        data = r.json()
        assert "tide_height_m_cd" in data
        assert "tide_height_m_msl" in data
        assert "tidal_phase" in data
        assert "tidal_locking_risk" in data

        # Scenarios
        r = await client.get("/api/v1/tide/scenarios")
        assert r.status_code == 200
        scenarios = r.json()
        assert len(scenarios) >= 5
        assert any(s["id"] == "rainfall_high_tide" for s in scenarios)

        # Forecast schedule
        r = await client.get("/api/v1/tide/forecast?scenario=rainfall_normal_tide&duration_hours=4.0")
        assert r.status_code == 200
        fc = r.json()
        assert fc["scenario"] == "rainfall_normal_tide"
        assert len(fc["schedule"]) > 0


@pytest.mark.asyncio
async def test_drainage_api_endpoints():
    """Verify /api/v1/drainage endpoints return valid metrics and facilities."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Status
        r = await client.get("/api/v1/drainage/status")
        assert r.status_code == 200
        status = r.json()
        assert "network_metrics" in status
        assert "pumping_infrastructure" in status
        assert status["pumping_infrastructure"]["total_stations"] == 8

        # Surcharge
        r = await client.get("/api/v1/drainage/surcharge?rainfall_intensity_mmh=50.0")
        assert r.status_code == 200
        surch = r.json()
        assert surch["rainfall_intensity_mmh"] == 50.0
        assert surch["overall_utilization_ratio"] >= 1.5

        # Pumping stations
        r = await client.get("/api/v1/drainage/pumping-stations")
        assert r.status_code == 200
        pumps = r.json()
        assert len(pumps["stations"]) == 8
        station_names = [s["name"] for s in pumps["stations"]]
        assert "Love Grove Pumping Station" in station_names
        assert "Britannia Pumping Station" in station_names


@pytest.mark.asyncio
async def test_impact_assessment_engine():
    """Verify flood impact assessment correctly computes exposure tiers."""
    # Test zero flood
    zero_impact = await compute_flood_impact(max_depth_m=0.01, flooded_cells=0, flooded_area_km2=0.0)
    assert zero_impact.severity_level == "NONE"
    assert zero_impact.population_exposed == 0

    # Test major flood scenario
    major_impact = await compute_flood_impact(max_depth_m=1.2, flooded_cells=500, flooded_area_km2=1.5)
    assert major_impact.severity_level in ("MAJOR", "CATASTROPHIC")
    assert major_impact.population_exposed > 0
    assert major_impact.population_in_danger_zone > 0
    assert major_impact.buildings_affected > 0
    assert major_impact.road_km_flooded > 0
    assert major_impact.hospitals_at_risk > 0


@pytest.mark.asyncio
async def test_impact_api_endpoints():
    """Verify /api/v1/impact endpoints return structured exposure packages."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Summary
        r = await client.get("/api/v1/impact/summary?max_depth_m=0.8&flooded_area_km2=0.5")
        assert r.status_code == 200
        summary = r.json()
        assert "population" in summary
        assert "buildings" in summary
        assert "roads" in summary
        assert "critical_infrastructure" in summary

        # Population
        r = await client.get("/api/v1/impact/population")
        assert r.status_code == 200
        pop = r.json()
        assert "population_exposed" in pop

        # Roads
        r = await client.get("/api/v1/impact/roads")
        assert r.status_code == 200
        roads = r.json()
        assert "road_km_flooded" in roads

        # Shelters
        r = await client.get("/api/v1/impact/shelters")
        assert r.status_code == 200
        shelters = r.json()
        assert "total_shelters" in shelters
        assert shelters["total_shelters"] > 0
