"""Abstract base class for rainfall data providers.

All rainfall providers implement this interface. The system is NOT
tightly coupled to any single API. New sources (MOSDAC, gauges, etc.)
are added by implementing a new provider.

Provider Pattern:
    RainfallProvider (ABC)
    ├── OpenMeteoProvider     — REST API, 15min/hourly, no key
    ├── MOSDACProvider        — ISRO satellite data
    ├── IMERGProvider         — NASA GPM
    ├── GaugeProvider         — CWPRS / Maharashtra telemetry
    └── SyntheticProvider     — Design storms for testing
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from packages.contracts.city import BoundingBox
from packages.contracts.rainfall import RainfallObservation


class RainfallProvider(ABC):
    """Abstract rainfall data provider.

    Every provider must implement:
    - fetch_current(): Get latest rainfall observation(s)
    - fetch_historical(): Get past rainfall for a time range
    - provider_name: Human-readable name for provenance tracking
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name for logging and provenance."""
        ...

    @abstractmethod
    async def fetch_current(
        self,
        latitude: float,
        longitude: float,
    ) -> list[RainfallObservation]:
        """Fetch current/latest rainfall observation(s) for a location.

        Args:
            latitude: WGS84 latitude
            longitude: WGS84 longitude

        Returns:
            List of rainfall observations (may be empty if no data)
        """
        ...

    @abstractmethod
    async def fetch_historical(
        self,
        latitude: float,
        longitude: float,
        start_date: datetime,
        end_date: datetime,
    ) -> list[RainfallObservation]:
        """Fetch historical rainfall data for a time range.

        Args:
            latitude: WGS84 latitude
            longitude: WGS84 longitude
            start_date: Start of time range (inclusive)
            end_date: End of time range (inclusive)

        Returns:
            List of rainfall observations, chronologically ordered
        """
        ...

    async def fetch_forecast(
        self,
        latitude: float,
        longitude: float,
        hours_ahead: int = 24,
    ) -> list[RainfallObservation]:
        """Fetch rainfall forecast (optional — not all providers support this).

        Default implementation returns empty list.
        Override in providers that support forecasting.
        """
        return []

    async def health_check(self) -> bool:
        """Check if the provider is accessible.

        Default implementation returns True.
        Override to implement actual connectivity checks.
        """
        return True
