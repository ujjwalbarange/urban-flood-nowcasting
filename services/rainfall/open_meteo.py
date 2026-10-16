"""Open-Meteo rainfall provider — free weather API, no key required.

Endpoints:
- Forecast: https://api.open-meteo.com/v1/forecast (current + 7-day hourly)
- Archive:  https://archive-api.open-meteo.com/v1/archive (historical from 1940)

Limits: 10,000 requests/day (free tier)
License: CC-BY 4.0

This is our PRIMARY rainfall provider for development and initial validation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog

from packages.contracts.provenance import DataQuality, DataSource, Provenance
from packages.contracts.rainfall import (
    NowcastMethod,
    RainfallNowcast,
    RainfallObservation,
    RainfallSpatialType,
)
from services.rainfall.base import RainfallProvider

logger = structlog.get_logger()

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


class OpenMeteoProvider(RainfallProvider):
    """Open-Meteo free weather API provider.

    Provides:
    - Current conditions (precipitation_probability, rain, showers)
    - Hourly forecasts up to 7 days ahead
    - Historical hourly data from 1940 to present (ERA5/ERA5-Land)
    """

    _last_current_cache: dict[str, tuple[float, list[RainfallObservation]]] = {}

    @property
    def provider_name(self) -> str:
        return "Open-Meteo"

    async def fetch_current(
        self,
        latitude: float,
        longitude: float,
    ) -> list[RainfallObservation]:
        """Fetch current weather including precipitation with cache and graceful fallback."""
        import time
        cache_key = f"{round(latitude, 3)},{round(longitude, 3)}"
        now_ts = time.time()

        if cache_key in self._last_current_cache:
            cached_time, cached_obs = self._last_current_cache[cache_key]
            if now_ts - cached_time < 60.0:  # 60-second cache
                return cached_obs

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "precipitation,rain,showers,weather_code",
            "hourly": "precipitation,rain,showers,precipitation_probability",
            "timezone": "auto",
            "forecast_days": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(FORECAST_URL, params=params)
                response.raise_for_status()
                data = response.json()

            observations = []
            current = data.get("current", {})
            if current:
                precip = current.get("precipitation", 0) or 0
                rain = current.get("rain", 0) or 0
                rate_mmh = max(precip, rain)

                obs = RainfallObservation(
                    source=DataSource.OPEN_METEO,
                    observed_at=datetime.now(timezone.utc),
                    rate_mmh=rate_mmh,
                    spatial_type=RainfallSpatialType.POINT,
                    latitude=latitude,
                    longitude=longitude,
                    quality=DataQuality.ESTIMATED,
                    provenance=Provenance(
                        source=DataSource.OPEN_METEO,
                        source_uri=FORECAST_URL,
                        processing_method="open_meteo_forecast_current",
                        quality=DataQuality.ESTIMATED,
                        notes="ERA5-based model output, not direct measurement",
                    ),
                )
                observations.append(obs)

            self._last_current_cache[cache_key] = (now_ts, observations)
            logger.info(
                "Fetched current rainfall",
                provider="open_meteo",
                lat=latitude,
                lon=longitude,
                rate_mmh=observations[0].rate_mmh if observations else 0,
            )
            return observations
        except Exception as exc:
            logger.warning("Open-Meteo fetch failed, returning cached or dry baseline", error=str(exc))
            if cache_key in self._last_current_cache:
                return self._last_current_cache[cache_key][1]
            return [
                RainfallObservation(
                    source=DataSource.OPEN_METEO,
                    observed_at=datetime.now(timezone.utc),
                    rate_mmh=0.0,
                    spatial_type=RainfallSpatialType.POINT,
                    latitude=latitude,
                    longitude=longitude,
                    quality=DataQuality.ESTIMATED,
                    provenance=Provenance(
                        source=DataSource.OPEN_METEO,
                        source_uri=FORECAST_URL,
                        processing_method="fallback_dry_baseline",
                        quality=DataQuality.ESTIMATED,
                        notes="External API timeout fallback",
                    ),
                )
            ]

    async def fetch_historical(
        self,
        latitude: float,
        longitude: float,
        start_date: datetime,
        end_date: datetime,
    ) -> list[RainfallObservation]:
        """Fetch historical hourly rainfall from ERA5/ERA5-Land archive."""
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start_date.strftime("%Y-%m-%d"),
            "end_date": end_date.strftime("%Y-%m-%d"),
            "hourly": "precipitation,rain",
            "timezone": "auto",
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(ARCHIVE_URL, params=params)
            response.raise_for_status()
            data = response.json()

        observations = []
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        precip_values = hourly.get("precipitation", [])
        rain_values = hourly.get("rain", precip_values)

        for i, time_str in enumerate(times):
            precip = precip_values[i] if i < len(precip_values) else 0
            rain = rain_values[i] if i < len(rain_values) else 0
            rate_mmh = max(precip or 0, rain or 0)

            try:
                obs_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            except ValueError:
                obs_time = datetime.fromisoformat(time_str)

            obs = RainfallObservation(
                source=DataSource.OPEN_METEO,
                observed_at=obs_time,
                rate_mmh=rate_mmh,
                spatial_type=RainfallSpatialType.POINT,
                latitude=latitude,
                longitude=longitude,
                quality=DataQuality.ESTIMATED,
            )
            observations.append(obs)

        logger.info(
            "Fetched historical rainfall",
            provider="open_meteo",
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            records=len(observations),
        )
        return observations

    async def fetch_forecast(
        self,
        latitude: float,
        longitude: float,
        hours_ahead: int = 24,
    ) -> list[RainfallObservation]:
        """Fetch hourly rainfall forecast up to 7 days ahead."""
        forecast_days = min(max(hours_ahead // 24 + 1, 1), 7)

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "precipitation,rain,showers,precipitation_probability",
            "timezone": "auto",
            "forecast_days": forecast_days,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(FORECAST_URL, params=params)
            response.raise_for_status()
            data = response.json()

        observations = []
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        precip_values = hourly.get("precipitation", [])
        prob_values = hourly.get("precipitation_probability", [])

        now = datetime.now(timezone.utc)

        for i, time_str in enumerate(times):
            if i >= hours_ahead:
                break

            precip = precip_values[i] if i < len(precip_values) else 0
            rate_mmh = precip or 0

            try:
                valid_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            except ValueError:
                valid_time = datetime.fromisoformat(time_str)

            # Only include future times
            if valid_time <= now:
                continue

            obs = RainfallObservation(
                source=DataSource.OPEN_METEO,
                observed_at=now,
                rate_mmh=rate_mmh,
                spatial_type=RainfallSpatialType.POINT,
                latitude=latitude,
                longitude=longitude,
                quality=DataQuality.ESTIMATED,
            )
            observations.append(obs)

        logger.info(
            "Fetched rainfall forecast",
            provider="open_meteo",
            hours_ahead=hours_ahead,
            records=len(observations),
        )
        return observations

    async def health_check(self) -> bool:
        """Check if Open-Meteo API is accessible."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    FORECAST_URL,
                    params={
                        "latitude": 19.076,
                        "longitude": 72.877,
                        "current": "precipitation",
                    },
                )
                return response.status_code == 200
        except Exception:
            return False
