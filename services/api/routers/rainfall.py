"""Rainfall API router — query rainfall data from multiple providers."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Query

from packages.contracts.rainfall import RainfallObservation
from services.config.providers import ProviderSettings
from services.rainfall.open_meteo import OpenMeteoProvider
from services.rainfall.synthetic import SyntheticProvider, StormType
from services.rainfall.imerg import IMERGProvider
from services.rainfall.mosdac import MOSDACProvider
from services.nowcast.persistence import PersistenceNowcaster

logger = structlog.get_logger()
router = APIRouter()

# Provider registry
_providers = {
    "open_meteo": OpenMeteoProvider(),
    "nasa_imerg": IMERGProvider(),
    "mosdac": MOSDACProvider(),
    "synthetic_uniform": SyntheticProvider(storm_type=StormType.UNIFORM),
    "synthetic_scs": SyntheticProvider(storm_type=StormType.SCS_TYPE_II),
}



@router.get("/rainfall/current")
async def get_current_rainfall(
    lat: float = Query(19.076, description="Latitude (WGS84)"),
    lon: float = Query(72.877, description="Longitude (WGS84)"),
    provider: str = Query("open_meteo", description="Provider name"),
):
    """Get current rainfall at a location."""
    if provider not in _providers:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    try:
        observations = await _providers[provider].fetch_current(lat, lon)
        return {
            "provider": provider,
            "latitude": lat,
            "longitude": lon,
            "observations": [obs.model_dump() for obs in observations],
        }
    except Exception as e:
        logger.error("Rainfall fetch failed", provider=provider, error=str(e))
        raise HTTPException(status_code=502, detail=f"Provider error: {str(e)}")


@router.get("/rainfall/historical")
async def get_historical_rainfall(
    lat: float = Query(19.076, description="Latitude (WGS84)"),
    lon: float = Query(72.877, description="Longitude (WGS84)"),
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    provider: str = Query("open_meteo", description="Provider name"),
):
    """Get historical rainfall for a time range."""
    if provider not in _providers:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    try:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if (end - start).days > 365:
        raise HTTPException(status_code=400, detail="Max date range is 365 days")

    try:
        observations = await _providers[provider].fetch_historical(lat, lon, start, end)
        total_depth = sum(o.rate_mmh for o in observations)  # Approximate cumulative
        return {
            "provider": provider,
            "latitude": lat,
            "longitude": lon,
            "start_date": start_date,
            "end_date": end_date,
            "record_count": len(observations),
            "approximate_total_mm": round(total_depth, 2),
            "observations": [obs.model_dump() for obs in observations[:500]],
            "truncated": len(observations) > 500,
        }
    except Exception as e:
        logger.error("Historical rainfall fetch failed", provider=provider, error=str(e))
        raise HTTPException(status_code=502, detail=f"Provider error: {str(e)}")


@router.get("/rainfall/forecast")
async def get_rainfall_forecast(
    lat: float = Query(19.076, description="Latitude (WGS84)"),
    lon: float = Query(72.877, description="Longitude (WGS84)"),
    hours: int = Query(24, ge=1, le=168, description="Hours ahead to forecast"),
    provider: str = Query("open_meteo", description="Provider name"),
):
    """Get rainfall forecast for a location."""
    if provider not in _providers:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    try:
        forecasts = await _providers[provider].fetch_forecast(lat, lon, hours)
        return {
            "provider": provider,
            "latitude": lat,
            "longitude": lon,
            "hours_ahead": hours,
            "record_count": len(forecasts),
            "forecasts": [f.model_dump() for f in forecasts],
        }
    except Exception as e:
        logger.error("Forecast fetch failed", provider=provider, error=str(e))
        raise HTTPException(status_code=502, detail=f"Provider error: {str(e)}")


@router.get("/rainfall/providers")
async def list_providers():
    """List available rainfall providers with capabilities and limitations."""
    statuses = {}
    for name, provider in _providers.items():
        try:
            healthy = await provider.health_check()
        except Exception:
            healthy = False
        statuses[name] = {
            "name": provider.provider_name,
            "healthy": healthy,
        }
    provider_catalog = ProviderSettings().status_catalog()
    return {
        "providers": statuses,
        "alternatives": {
            name: status.model_dump(mode="json")
            for name, status in provider_catalog.items()
            if name in {"nasa_gpm_imerg", "open_meteo", "mosdac"}
        },
        "notice": "Provider readiness is configuration status, not evidence that any local data are verified observations.",
    }


@router.get("/rainfall/nowcast")
async def get_rainfall_nowcast(
    lat: float = Query(19.076, description="Latitude (WGS84)"),
    lon: float = Query(72.877, description="Longitude (WGS84)"),
    horizon_minutes: int = Query(120, ge=15, le=360, description="Nowcast horizon in minutes"),
    provider: str = Query("open_meteo", description="Rainfall provider name for initial state"),
):
    """Generate short-horizon (15 to 120 min) nowcasting with confidence decay."""
    if provider not in _providers:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    try:
        obs_list = await _providers[provider].fetch_current(lat, lon)
        current_rate = obs_list[0].rate_mmh if obs_list else 0.0
    except Exception:
        current_rate = 0.0

    nowcaster = PersistenceNowcaster(time_step_minutes=15)
    forecasts = nowcaster.nowcast(
        current_rate_mmh=current_rate,
        hours_ahead=horizon_minutes / 60.0,
        latitude=lat,
        longitude=lon,
    )

    return {
        "provider": provider,
        "latitude": lat,
        "longitude": lon,
        "current_rate_mmh": current_rate,
        "horizon_minutes": horizon_minutes,
        "method": "Lagrangian Persistence with Exponential Decay",
        "provenance_note": f"Input derived from {provider}. Satellite or model precipitation != ground gauge observation.",
        "steps": [f.model_dump() for f in forecasts],
    }


@router.get("/rainfall/mosdac/status")
async def get_mosdac_status():
    """Get live status and operational telemetry for ISRO MOSDAC satellite integration."""
    mosdac: MOSDACProvider = _providers["mosdac"]
    try:
        await mosdac.health_check()
    except Exception as e:
        logger.warning("MOSDAC health check exception", error=str(e))
    return mosdac.get_status_details()


@router.get("/rainfall/mosdac/granules")
async def get_mosdac_granules(count: int = Query(5, ge=1, le=20)):
    """Search latest INSAT-3DR/3DS Level-2B HEM granules from ISRO MOSDAC."""
    mosdac: MOSDACProvider = _providers["mosdac"]
    granules = await mosdac.search_latest_granules(count=count)
    return {
        "provider": "ISRO MOSDAC",
        "dataset_id": mosdac.dataset_id,
        "count": len(granules),
        "granules": granules,
    }


@router.get("/rainfall/imerg/status")
async def get_imerg_status():
    """Get live status and operational telemetry for NASA Earthdata GPM IMERG."""
    imerg: IMERGProvider = _providers["nasa_imerg"]
    try:
        await imerg.health_check()
    except Exception as e:
        logger.warning("IMERG health check exception", error=str(e))
    return imerg.get_status_details()


@router.get("/rainfall/imerg/granules")
async def get_imerg_granules(limit: int = Query(5, ge=1, le=20)):
    """Search recent GPM IMERG satellite precipitation granules from NASA CMR."""
    imerg: IMERGProvider = _providers["nasa_imerg"]
    granules = await imerg.search_live_granules(limit=limit)
    return {
        "provider": "NASA Earthdata CMR",
        "dataset_id": "GPM_3IMERGHHL",
        "count": len(granules),
        "granules": [
            {
                "title": g.get("title"),
                "time_start": g.get("time_start"),
                "updated": g.get("updated"),
                "links": [l.get("href") for l in g.get("links", []) if "href" in l][:2],
            }
            for g in granules
        ],
    }
