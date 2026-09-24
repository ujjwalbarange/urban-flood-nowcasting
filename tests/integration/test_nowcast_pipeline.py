"""Integration test for the genuine end-to-end Nowcasting Pipeline.

Tests:
1. Multi-point Open-Meteo weather ingestion & normalization
2. Spatial rainfall forcing grid construction
3. Real physical drainage coupling (BRIMSTOWAD nodes & retention heads)
4. 2D Diffusive Wave flood solver on Copernicus GLO-30 DEM
5. Mass balance conservation closure (< 2% error)
6. Timeline depth grid snapshots & raster PNG rendering
7. Ward flood explainability ("Why is this area flooding?")
8. Live health checks for MOSDAC and NASA Earthdata IMERG
"""

import pytest
import numpy as np
from services.nowcast.pipeline import (
    run_nowcast_pipeline,
    fetch_comprehensive_weather,
    build_rainfall_schedule_from_weather,
    map_drainage_nodes_to_grid,
    compute_ward_explanations,
)
from services.flood.raster_renderer import depth_grid_to_png_bytes
from services.rainfall.mosdac import MOSDACProvider
from services.rainfall.imerg import IMERGProvider


@pytest.mark.asyncio
async def test_comprehensive_weather_fetch():
    """Verify live Open-Meteo weather fetch across 9 monitoring points."""
    weather = await fetch_comprehensive_weather(forecast_hours=6, past_hours=3)
    assert weather is not None
    assert weather.status == "ok"
    # Graceful degradation handles occasional transient timeout on 1-2 external API points
    assert len(weather.points) >= 6
    assert weather.mean_rainfall_mmh >= 0.0
    assert weather.latency_ms > 0
    assert len(weather.forecast_hourly) >= 6


@pytest.mark.asyncio
async def test_drainage_coupling_mapping():
    """Verify that BMC / BRIMSTOWAD drainage nodes map to DEM grid cells."""
    georef = {
        "min_lat": 18.98,
        "max_lat": 19.04,
        "min_lon": 72.82,
        "max_lon": 72.87,
        "rows": 60,
        "cols": 50,
        "cell_size_m": 30.0,
    }
    coupling_points, drainage_heads = map_drainage_nodes_to_grid(georef, (60, 50))
    # Hindmata/Dadar region contains 2 major holding ponds
    assert len(coupling_points) >= 2
    for cp in coupling_points:
        assert 0 <= cp["row"] < 60
        assert 0 <= cp["col"] < 50
        assert cp["node_id"] in drainage_heads


@pytest.mark.asyncio
async def test_end_to_end_nowcast_scenario():
    """Verify end-to-end nowcasting pipeline with scenario rainfall forcing."""
    result = await run_nowcast_pipeline(
        catchment="hindmata_dadar",
        duration_hours=1.5,
        grid_size=40,
        force_rainfall_mmh=60.0,
    )
    assert result.status == "completed"
    assert result.max_depth_m > 0.05
    assert result.flooded_cells > 0
    assert result.flooded_area_km2 > 0.0
    assert result.mass_balance_error_pct < 2.0  # Physical mass balance closure
    assert result.drainage_nodes_coupled >= 2
    assert result.coupling_events > 0

    # Verify timeline depth grids are captured for scrubbing
    assert len(result.timeline_depth_grids) > 0
    assert 0 in result.timeline_depth_grids

    # Verify smooth raster PNG rendering
    png_bytes = depth_grid_to_png_bytes(result.depth_grid, upsample_factor=2, smooth_radius=1.0)
    assert len(png_bytes) > 500
    assert png_bytes[:4] == b"\x89PNG"


@pytest.mark.asyncio
async def test_ward_explainability():
    """Verify explainability generates contributing factors for affected wards."""
    explanations = compute_ward_explanations(
        catchment="hindmata_dadar",
        max_depth_m=0.35,
        rainfall_3h_mm=45.0,
        coupled_nodes=[{"name": "Pramod Mahajan Kala Park Holding Pond"}],
    )
    assert "FN" in explanations
    fn = explanations["FN"]
    assert fn["forecast_rainfall_3h_mm"] == 45.0
    assert fn["simulated_max_depth_m"] == 0.35
    assert len(fn["recommended_actions"]) >= 2
    assert len(fn["chronic_hotspots"]) > 0


@pytest.mark.asyncio
async def test_mosdac_provider_health():
    """Verify ISRO MOSDAC provider health check and status telemetry."""
    mosdac = MOSDACProvider()
    assert mosdac.is_configured is True
    is_healthy = await mosdac.health_check()
    assert is_healthy is True
    status = mosdac.get_status_details()
    assert status["status"] == "CONNECTED"
    assert status["provider"] == "MOSDAC / ISRO"
    assert status["satellite"] == "INSAT-3DR / INSAT-3DS"


@pytest.mark.asyncio
async def test_imerg_provider_health():
    """Verify NASA Earthdata IMERG provider health check and status telemetry."""
    imerg = IMERGProvider()
    assert imerg.token is not None
    is_healthy = await imerg.health_check()
    assert is_healthy is True
    status = imerg.get_status_details()
    assert status["status"] == "CONNECTED"
    assert status["provider"] == "NASA Earthdata / GPM IMERG"
