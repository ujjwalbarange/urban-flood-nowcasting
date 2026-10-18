"""Automated Unit and Integration Tests for MUFNS Phase 2:

- Weather intelligence service and coordinate validation
- Current weather normalization and precipitation vs rain physics distinction
- 7-day daily and 48-hour hourly NWP forecast parsing
- Missing or null meteorological variable handling
- Upstream failure, timeout handling, and stale cache labeling
- ERA5-Land historical monsoon reanalysis percentiles and rolling accumulation extremes
- 2016-2025 verified flood incident spatial matching
- Weather analogue storm matching and transparent scientific risk distinction
- API endpoints integration and Phase 1 backwards compatibility
"""

import pytest
import json
import httpx
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from services.weather.weather_service import LocationWeatherService, get_weather_service, WMO_CODE_MAP
from services.data.store import get_data_store


@pytest.fixture
def repo_root():
    return Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def weather_service():
    return LocationWeatherService()


def test_wmo_code_mapping():
    """Verify WMO weather codes map to sensible textual descriptions and keys."""
    assert WMO_CODE_MAP[0] == ("Clear Sky", "clear")
    assert WMO_CODE_MAP[3] == ("Overcast", "overcast")
    assert WMO_CODE_MAP[65] == ("Heavy Rain", "rain_heavy")
    assert WMO_CODE_MAP[95] == ("Thunderstorm", "thunderstorm")


def test_coordinate_validation(weather_service):
    """Ensure coordinates within Mumbai domain pass and far-flung coordinates fail."""
    # Inside Mumbai / MMR
    is_valid, _ = weather_service.validate_coordinates(18.932, 72.835)
    assert is_valid is True

    is_valid, _ = weather_service.validate_coordinates(19.218, 72.978)
    assert is_valid is True

    # Outside domain (e.g., Delhi, Equator, London)
    is_valid, msg = weather_service.validate_coordinates(28.6139, 77.2090)
    assert is_valid is False
    assert "outside" in msg.lower()

    is_valid, msg = weather_service.validate_coordinates(0.0, 0.0)
    assert is_valid is False


def test_current_weather_and_forecast_normalization(weather_service):
    """Verify normalization of raw Open-Meteo payload into structured contract."""
    mock_raw = {
        "latitude": 19.076,
        "longitude": 72.877,
        "timezone": "Asia/Kolkata",
        "elevation": 14.0,
        "current": {
            "time": "2026-10-18T12:00",
            "temperature_2m": 32.5,
            "apparent_temperature_c": 38.0,
            "relative_humidity_2m": 65,
            "precipitation": 12.0,
            "rain": 4.0,
            "showers": 8.0,
            "weather_code": 81,
            "surface_pressure": 1010.5,
            "wind_speed_10m": 15.2,
            "wind_direction_10m": 240,
            "wind_gusts_10m": 28.5,
        },
        "daily": {
            "time": ["2026-10-18", "2026-10-19", "2026-10-20"],
            "weather_code": [81, 65, 3],
            "temperature_2m_max": [33.0, 31.0, 32.0],
            "temperature_2m_min": [26.0, 25.0, 26.0],
            "precipitation_sum": [45.0, 85.0, 5.0],
            "rain_sum": [15.0, 40.0, 5.0],
            "showers_sum": [30.0, 45.0, 0.0],
            "precipitation_hours": [6.0, 12.0, 1.0],
            "precipitation_probability_max": [85, 95, 20],
            "wind_speed_10m_max": [25.0, 35.0, 18.0],
            "wind_gusts_10m_max": [40.0, 55.0, 25.0],
        },
        "hourly": {
            "time": [f"2026-10-18T{h:02d}:00" for h in range(24)],
            "precipitation": [2.5 if 10 <= h <= 15 else 0.0 for h in range(24)],
            "rain": [1.0 if 10 <= h <= 15 else 0.0 for h in range(24)],
            "precipitation_probability": [80 if 10 <= h <= 15 else 10 for h in range(24)],
            "temperature_2m": [30.0] * 24,
            "weather_code": [81 if 10 <= h <= 15 else 1 for h in range(24)],
            "wind_speed_10m": [12.0] * 24,
        }
    }

    normalized = weather_service._normalize_forecast_response(mock_raw, 19.076, 72.877)

    assert normalized["status"] == "SUCCESS"
    curr = normalized["current"]
    assert curr["temperature_c"] == 32.5
    assert curr["precipitation_mm"] == 12.0
    assert curr["stratiform_rain_mm"] == 4.0
    assert curr["convective_showers_mm"] == 8.0
    assert curr["effective_rainfall_rate_mmh"] == 12.0
    assert curr["weather_description"] == "Moderate Rain Showers"
    assert curr["timezone"] == "Asia/Kolkata"

    daily = normalized["daily_forecast"]
    assert len(daily) == 3
    assert daily[0]["precipitation_sum_mm"] == 45.0
    assert daily[1]["precipitation_sum_mm"] == 85.0

    peak = normalized["peak_summary"]
    assert peak["peak_hourly_rate_mmh"] == 2.5
    assert peak["forecast_24h_accumulation_mm"] == 15.0  # 6 hours * 2.5 mm


def test_missing_or_null_variables_handling(weather_service):
    """Payload with null or missing attributes should not raise errors."""
    mock_sparse = {
        "latitude": 19.016,
        "longitude": 72.853,
        "current": {
            "temperature_2m": None,
            "precipitation": None,
            "rain": None,
            "showers": None,
            "weather_code": None,
            "wind_speed_10m": None,
        },
        "daily": {},
        "hourly": {},
    }

    normalized = weather_service._normalize_forecast_response(mock_sparse, 19.016, 72.853)
    curr = normalized["current"]
    assert curr["temperature_c"] is None
    assert curr["precipitation_mm"] == 0.0
    assert curr["effective_rainfall_rate_mmh"] == 0.0
    assert curr["weather_description"] in {"Unknown", "Clear Sky"}


@pytest.mark.asyncio
async def test_upstream_timeout_and_stale_cache_fallback(weather_service):
    """Ensure upstream timeout gracefully serves cached data with stale flag."""
    lat, lon = 19.076, 72.877
    cache_key = weather_service._get_cache_key(lat, lon)

    # Seed cache with known data
    dummy_data = {
        "status": "SUCCESS",
        "current": {"temperature_c": 30.0, "effective_rainfall_rate_mmh": 0.0},
        "daily_forecast": [],
        "hourly_forecast": [],
        "peak_summary": None,
    }
    weather_service._forecast_cache[cache_key] = (1000.0, dummy_data)

    # Create a mock client that raises a ConnectTimeout
    mock_client = AsyncMock()
    mock_client.get.side_effect = httpx.ConnectTimeout("Open-Meteo connection timed out")

    result = await weather_service.fetch_current_and_forecast(lat, lon, client=mock_client)

    assert result["from_cache"] is True
    assert result["is_stale"] is True
    assert "upstream_error" in result
    assert result["current"]["temperature_c"] == 30.0


@pytest.mark.asyncio
async def test_historical_weather_comparison_and_percentiles(weather_service):
    """Verify historical monsoon distribution percentiles and rank assignment."""
    lat, lon = 19.076, 72.877
    # Test with typical moderate monsoon rain (10 mm/h, 50 mm in 24h)
    comp = await weather_service.fetch_historical_weather_comparison(
        lat, lon, current_rate_mmh=10.0, forecast_24h_mm=50.0
    )

    assert "hourly_percentiles" in comp
    assert "daily_24h_percentiles" in comp
    assert "rolling_max_mm" in comp

    h_pct = comp["hourly_percentiles"]
    assert h_pct["p50"] <= h_pct["p75"] <= h_pct["p90"] <= h_pct["p95"] <= h_pct["p99"]
    assert h_pct["record_max"] >= h_pct["p99"]

    # Verify ranking
    rank_info = comp["comparison"]
    assert "Percentile" in rank_info["current_hourly_percentile_rank"] or "Dry" in rank_info["current_hourly_percentile_rank"]
    assert rank_info["current_severity"] in {"NORMAL", "LOW", "MODERATE", "HIGH", "VERY_HIGH", "CRITICAL"}


def test_historical_flood_evidence_and_analogue_matching(weather_service):
    """Verify spatial retrieval of real 2016-2025 flood events and weather analogue matching."""
    # Test coordinates near Dadar / Hindmata (chronic flood corridor)
    lat, lon = 19.018, 72.843
    evidence = weather_service.fetch_historical_flood_evidence(
        lat=lat, lon=lon, ward_id="F/N", radius_km=5.0, forecast_24h_mm=120.0, forecast_peak_mmh=35.0
    )

    assert evidence["source"].startswith("IMD Santacruz")
    assert evidence["nearby_records_count"] > 0
    assert len(evidence["nearby_records"]) > 0

    first_ev = evidence["nearby_records"][0]
    assert "flood_depth_cm" in first_ev
    assert "locality" in first_ev
    assert "distance_km" in first_ev
    assert first_ev["distance_km"] <= 5.0

    # Verify weather analogue storms
    analogues = evidence["weather_analogue_storms"]
    assert len(analogues) == 3
    assert "similarity_delta" in analogues[0]


def test_transparent_hazard_assessment_and_scientific_disclaimer(weather_service):
    """Verify that hazard assessment explicitly separates weather similarity from calibrated flood probabilities."""
    hist_comp = {
        "hourly_percentiles": {"p75": 1.4, "p90": 6.8, "p95": 14.5, "p99": 42.0},
        "daily_24h_percentiles": {"p50": 12.0, "p75": 38.5, "p90": 85.0, "p95": 140.0, "p99": 235.0},
    }
    flood_ev = {
        "has_local_evidence": True,
        "weather_analogue_storms": [{
            "date": "2019-07-02",
            "rainfall_24h_mm": 135.0,
            "flood_depth_cm": 65.0,
            "locality": "Milan Subway",
        }]
    }

    # Heavy rainfall scenario
    hazard = weather_service.compute_hazard_assessment(
        current_rate_mmh=25.0,
        forecast_24h_mm=130.0,
        historical_comp=hist_comp,
        flood_evidence=flood_ev,
    )

    assert hazard["hazard_level"] in {"HIGH_HAZARD", "VERY_HIGH_HAZARD"}
    assert "Orange" in hazard["headline"] or "Heavy" in hazard["headline"]
    assert "2019-07-02" in hazard["weather_analogue_narrative"]
    assert "65.0 cm" in hazard["weather_analogue_narrative"]

    # Critical Scientific Disclaimer requirement
    disclaimer = hazard["scientific_disclaimer"]
    assert "CRITICAL SCIENTIFIC DISTINCTION" in disclaimer
    assert "NOT a calibrated deterministic flood probability" in disclaimer


@pytest.mark.asyncio
async def test_full_weather_intelligence_aggregation(weather_service):
    """Integration test verifying full aggregation pipeline for Ward A coordinates."""
    res = await weather_service.get_full_weather_intelligence(
        lat=18.932, lon=72.835, ward_id="A", radius_km=5.0
    )

    assert res["status"] == "SUCCESS"
    assert res["coordinates"] == {"lat": 18.932, "lon": 72.835}
    assert res["ward_id"] == "A"
    assert "current_conditions" in res
    assert "forecast_7day" in res
    assert "historical_comparison" in res
    assert "historical_flood_evidence" in res
    assert "hazard_assessment" in res
