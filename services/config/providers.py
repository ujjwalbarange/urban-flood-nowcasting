"""Provider configuration and capability declarations.

Configuration answers whether a provider is ready without returning a token,
password or endpoint query that could contain a secret.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderReadiness(str, Enum):
    READY = "ready"
    CONFIGURATION_REQUIRED = "configuration_required"
    DOCUMENTATION_REQUIRED = "documentation_required"


class ProviderCapability(str, Enum):
    CURRENT = "current"
    HISTORICAL = "historical"
    FORECAST = "forecast"
    TERRAIN_DOWNLOAD = "terrain_download"
    FLOOD_EXTENT_EVIDENCE = "flood_extent_evidence"


class ProviderStatus(BaseSettings):
    """Safe, serializable provider state for API clients and audit logs."""

    name: str
    readiness: ProviderReadiness
    capabilities: set[ProviderCapability]
    origin_label: str
    limitations: list[str]


class ProviderSettings(BaseSettings):
    """Environment-backed configuration; secrets remain excluded from dumps."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    opentopography_api_key: Optional[str] = Field(default=None, repr=False)
    nasa_earthdata_token: Optional[str] = Field(default=None, repr=False)
    nasa_earthdata_username: Optional[str] = Field(default=None, repr=False)
    nasa_earthdata_password: Optional[str] = Field(default=None, repr=False)
    mosdac_user_email: Optional[str] = Field(default=None, repr=False)
    mosdac_pass: Optional[str] = Field(default=None, repr=False)
    mosdac_api_url: Optional[str] = None
    mosdac_token: Optional[str] = Field(default=None, repr=False)
    geospatial_ingestion_path: Path = Path("data/storage/geospatial")

    def status_catalog(self) -> dict[str, ProviderStatus]:
        mosdac_ready = bool(
            self.mosdac_user_email or self.mosdac_pass or os.getenv("MOSDAC_user_email")
        )
        return {
            "opentopography_cop30": ProviderStatus(
                name="OpenTopography COP30",
                readiness=(ProviderReadiness.READY if self.opentopography_api_key else ProviderReadiness.CONFIGURATION_REQUIRED),
                capabilities={ProviderCapability.TERRAIN_DOWNLOAD},
                origin_label="public_data",
                limitations=["30 m DSM is a coarse prototype terrain input, not a survey-grade urban DTM."],
            ),
            "nasa_gpm_imerg": ProviderStatus(
                name="NASA GPM IMERG",
                readiness=(ProviderReadiness.READY if self.nasa_earthdata_token or self.nasa_earthdata_username else ProviderReadiness.CONFIGURATION_REQUIRED),
                capabilities={ProviderCapability.CURRENT, ProviderCapability.HISTORICAL},
                origin_label="public_data",
                limitations=["Satellite rainfall is approximately 0.1 degree and is not a Mumbai gauge observation."],
            ),
            "open_meteo": ProviderStatus(
                name="Open-Meteo / reanalysis and NWP",
                readiness=ProviderReadiness.READY,
                capabilities={ProviderCapability.CURRENT, ProviderCapability.HISTORICAL, ProviderCapability.FORECAST},
                origin_label="derived_or_modelled",
                limitations=["Use as a public alternative; it is not a direct station measurement or street-scale nowcast."],
            ),
            "mosdac": ProviderStatus(
                name="MOSDAC / ISRO INSAT-3DR/3DS",
                readiness=(ProviderReadiness.READY if mosdac_ready else ProviderReadiness.CONFIGURATION_REQUIRED),
                capabilities={ProviderCapability.CURRENT, ProviderCapability.HISTORICAL},
                origin_label="public_data",
                limitations=["INSAT-3DR/3DS Level-2B Hydro-Estimator Method precipitation at ~4 km regional nadir."],
            ),
            "sentinel_1": ProviderStatus(
                name="Sentinel-1 GRD",
                readiness=ProviderReadiness.CONFIGURATION_REQUIRED,
                capabilities={ProviderCapability.FLOOD_EXTENT_EVIDENCE},
                origin_label="public_data",
                limitations=["Supports event flood-extent evidence after scene and method review; it does not measure water depth."],
            ),
        }
