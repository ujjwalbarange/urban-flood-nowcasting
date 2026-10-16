"""Rainfall provider services — multi-provider adapter pattern."""

from services.rainfall.base import RainfallProvider
from services.rainfall.open_meteo import OpenMeteoProvider
from services.rainfall.synthetic import SyntheticProvider, StormType
from services.rainfall.imerg import IMERGProvider
from services.rainfall.insat_service import INSAT3DRProvider
from services.rainfall.rainfall_fusion import RainfallFusionEngine, RainfallFusionMode

__all__ = [
    "RainfallProvider",
    "OpenMeteoProvider",
    "SyntheticProvider",
    "StormType",
    "IMERGProvider",
    "INSAT3DRProvider",
    "RainfallFusionEngine",
    "RainfallFusionMode",
]


