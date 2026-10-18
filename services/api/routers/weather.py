"""Weather Intelligence API Router.

Provides point-specific live weather, 7-day forecasts, ERA5 historical comparisons,
and documented flood-incident analogue intelligence for Mumbai coordinates.
"""

from __future__ import annotations

from typing import Optional
import structlog
from fastapi import APIRouter, HTTPException, Query

from services.weather.weather_service import get_weather_service

logger = structlog.get_logger()
router = APIRouter(prefix="/weather", tags=["weather-intelligence"])


@router.get("/intelligence")
async def get_weather_intelligence(
    lat: float = Query(..., description="Latitude (e.g. 19.076)"),
    lon: float = Query(..., description="Longitude (e.g. 72.877)"),
    ward_id: Optional[str] = Query(None, description="BMC Ward ID (e.g. 'A', 'H/E', 'RS')"),
    radius_km: float = Query(5.0, ge=1.0, le=20.0, description="Spatial search radius for historical flood records in km"),
):
    """Return comprehensive point-specific weather intelligence.

    Includes:
    - Current conditions (temperature, humidity, precipitation, rain, showers, pressure, wind)
    - 7-day daily forecast and 48-hour hourly NWP projections
    - ERA5 reanalysis historical comparison (percentiles, rolling extremes, antecedent wetness)
    - 2016-2025 verified flood evidence and weather analogue storm matches
    - Transparent hazard assessment distinguishing weather similarity from calibrated flood probabilities
    """
    svc = get_weather_service()
    is_valid, msg = svc.validate_coordinates(lat, lon)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)

    try:
        data = await svc.get_full_weather_intelligence(lat=lat, lon=lon, ward_id=ward_id, radius_km=radius_km)
        return data
    except Exception as exc:
        logger.error("Weather intelligence fetch failed", lat=lat, lon=lon, error=str(exc))
        raise HTTPException(status_code=502, detail=f"Weather service failed: {str(exc)}")


@router.get("/current")
async def get_location_current_weather(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
):
    """Get point-specific current weather observations / NWP estimates."""
    svc = get_weather_service()
    is_valid, msg = svc.validate_coordinates(lat, lon)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)

    res = await svc.fetch_current_and_forecast(lat, lon)
    if res.get("status") == "UPSTREAM_UNAVAILABLE":
        raise HTTPException(status_code=503, detail=res.get("error"))
    return {
        "status": "SUCCESS",
        "coordinates": {"lat": lat, "lon": lon},
        "current": res.get("current"),
        "from_cache": res.get("from_cache", False),
        "is_stale": res.get("is_stale", False),
    }


@router.get("/forecast")
async def get_location_forecast(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
):
    """Get 7-day daily and 48-hour hourly forecast for exact coordinates."""
    svc = get_weather_service()
    is_valid, msg = svc.validate_coordinates(lat, lon)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)

    res = await svc.fetch_current_and_forecast(lat, lon)
    if res.get("status") == "UPSTREAM_UNAVAILABLE":
        raise HTTPException(status_code=503, detail=res.get("error"))
    return {
        "status": "SUCCESS",
        "coordinates": {"lat": lat, "lon": lon},
        "daily_forecast": res.get("daily_forecast", []),
        "hourly_forecast": res.get("hourly_forecast", []),
        "peak_summary": res.get("peak_summary"),
        "from_cache": res.get("from_cache", False),
        "is_stale": res.get("is_stale", False),
    }


@router.get("/historical-comparison")
async def get_location_historical_comparison(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    current_rate: float = Query(0.0, ge=0.0, description="Current rain rate in mm/h"),
    forecast_24h: float = Query(0.0, ge=0.0, description="Forecast 24h accumulation in mm"),
):
    """Compare point-specific conditions with ERA5-Land monsoon rainfall percentiles."""
    svc = get_weather_service()
    is_valid, msg = svc.validate_coordinates(lat, lon)
    if not is_valid:
        raise HTTPException(status_code=400, detail=msg)

    return await svc.fetch_historical_weather_comparison(
        lat, lon, current_rate_mmh=current_rate, forecast_24h_mm=forecast_24h
    )


@router.get("/flood-evidence")
async def get_location_flood_evidence(
    lat: float = Query(..., description="Latitude"),
    lon: float = Query(..., description="Longitude"),
    ward_id: Optional[str] = Query(None, description="BMC Ward ID"),
    radius_km: float = Query(5.0, ge=1.0, le=20.0, description="Search radius in km"),
    forecast_24h: float = Query(0.0, ge=0.0, description="Forecast 24h accumulation in mm"),
):
    """Retrieve verified historical flood incident records and weather analogue storms."""
    svc = get_weather_service()
    return svc.fetch_historical_flood_evidence(
        lat, lon, ward_id=ward_id, radius_km=radius_km, forecast_24h_mm=forecast_24h
    )
