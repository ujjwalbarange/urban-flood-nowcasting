"""INSAT-3DR Satellite Rainfall Service — Local PostGIS Ingested Granules.

Provides operational querying, temporal accumulation, spatial clipping,
and raster grid extraction for INSAT-3DR Level-2B products:
- HEM: Hydro-Estimator Method Precipitation Rate (Primary Satellite Product)
- IMC: IMAGER Precipitation Retrieval (Secondary / Validation Product)

Supports:
- 30-min rate extraction
- 1h, 3h, 6h, 12h, 24h cumulative rainfall calculation
- Antecedent precipitation indexing
- Core Greater Mumbai spatial subsetting (72.77°E - 73.04°E, 18.89°N - 19.34°N)
- Full 1° x 1° marine approach corridor preservation (72.00°E - 73.01°E, 18.00°N - 19.01°N)
"""

from __future__ import annotations

import os
import ssl
import json
from datetime import datetime, timezone, timedelta
from typing import Any, Optional, Literal
from pathlib import Path
import asyncpg
import numpy as np
import rasterio
from dotenv import load_dotenv

load_dotenv()

from packages.contracts.city import BoundingBox
from packages.contracts.provenance import DataOrigin, DataQuality, DataSource, Provenance
from packages.contracts.rainfall import RainfallObservation, RainfallSpatialType
from services.rainfall.base import RainfallProvider

# Core Greater Mumbai bounds
MUMBAI_WEST = 72.77
MUMBAI_EAST = 73.04
MUMBAI_SOUTH = 18.89
MUMBAI_NORTH = 19.34


class INSAT3DRProvider(RainfallProvider):
    """INSAT-3DR satellite rainfall provider querying PostGIS and local COGs."""

    def __init__(
        self,
        product: Literal["HEM", "IMC"] = "HEM",
        db_url: Optional[str] = None,
    ):
        self.product = product.upper()
        raw_url = db_url or os.environ.get("DATABASE_URL", "")
        self.clean_url = raw_url.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]
        
        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE

    @property
    def provider_name(self) -> str:
        role = "Primary" if self.product == "HEM" else "Secondary/Validation"
        return f"ISRO MOSDAC INSAT-3DR ({self.product} - {role})"

    async def _get_conn(self) -> asyncpg.Connection:
        return await asyncpg.connect(self.clean_url, ssl=self.ssl_ctx)

    async def health_check(self) -> bool:
        """Verify that PostGIS table satellite_rainfall_observations has records."""
        try:
            conn = await self._get_conn()
            count = await conn.fetchval(
                "SELECT count(*) FROM public.satellite_rainfall_observations WHERE product = $1;",
                self.product
            )
            await conn.close()
            return count > 0
        except Exception:
            return False

    async def fetch_current(
        self,
        latitude: float,
        longitude: float,
    ) -> list[RainfallObservation]:
        """Fetch the latest available satellite observation for the study area."""
        conn = await self._get_conn()
        row = await conn.fetchrow("""
            SELECT observation_id, observation_time, mean_value, max_value,
                   mumbai_core_mean_value, spatial_resolution_km, canonical_file_path
            FROM public.satellite_rainfall_observations
            WHERE product = $1
            ORDER BY observation_time DESC LIMIT 1;
        """, self.product)
        await conn.close()

        if not row:
            return []

        rate = row["mumbai_core_mean_value"] if row["mumbai_core_mean_value"] is not None else row["mean_value"]
        
        return [
            RainfallObservation(
                source=DataSource.MOSDAC,
                observed_at=row["observation_time"],
                rate_mmh=max(0.0, float(rate or 0.0)),
                spatial_type=RainfallSpatialType.GRID,
                latitude=latitude,
                longitude=longitude,
                grid_storage_uri=row["canonical_file_path"],
                quality=DataQuality.MEASURED,
                provenance=Provenance(
                    source=DataSource.MOSDAC,
                    origin=DataOrigin.MEASURED_REAL,
                    retrieved_at=datetime.now(timezone.utc),
                    notes=f"INSAT-3DR {self.product} satellite retrieval. Granule: {row['observation_id']}"
                )
            )
        ]

    async def fetch_historical(
        self,
        latitude: float,
        longitude: float,
        start_date: datetime,
        end_date: datetime,
    ) -> list[RainfallObservation]:
        """Fetch chronologically ordered observations within a time range."""
        conn = await self._get_conn()
        rows = await conn.fetch("""
            SELECT observation_id, observation_time, mean_value, max_value,
                   mumbai_core_mean_value, mumbai_core_max_value, canonical_file_path
            FROM public.satellite_rainfall_observations
            WHERE product = $1
              AND observation_time >= $2
              AND observation_time <= $3
            ORDER BY observation_time ASC;
        """, self.product, start_date, end_date)
        await conn.close()

        obs_list = []
        for r in rows:
            rate = r["mumbai_core_mean_value"] if r["mumbai_core_mean_value"] is not None else r["mean_value"]
            obs_list.append(
                RainfallObservation(
                    source=DataSource.MOSDAC,
                    observed_at=r["observation_time"],
                    rate_mmh=max(0.0, float(rate or 0.0)),
                    spatial_type=RainfallSpatialType.GRID,
                    latitude=latitude,
                    longitude=longitude,
                    grid_storage_uri=r["canonical_file_path"],
                    quality=DataQuality.MEASURED,
                    provenance=Provenance(
                        source=DataSource.MOSDAC,
                        origin=DataOrigin.MEASURED_REAL,
                        retrieved_at=datetime.now(timezone.utc),
                        notes=f"INSAT-3DR {self.product} granule {r['observation_id']}"
                    )
                )
            )
        return obs_list

    async def get_raster_grid(
        self,
        observation_id: Optional[str] = None,
        obs_time: Optional[datetime] = None,
    ) -> Optional[dict[str, Any]]:
        """Retrieve full 28x28 raster grid for a specific granule or timestamp."""
        conn = await self._get_conn()
        if observation_id:
            row = await conn.fetchrow("""
                SELECT observation_id, observation_time, product, min_value, max_value,
                       mean_value, spatial_resolution_deg, canonical_file_path, grid_data, attributes
                FROM public.satellite_rainfall_observations
                WHERE observation_id = $1;
            """, observation_id)
        elif obs_time:
            row = await conn.fetchrow("""
                SELECT observation_id, observation_time, product, min_value, max_value,
                       mean_value, spatial_resolution_deg, canonical_file_path, grid_data, attributes
                FROM public.satellite_rainfall_observations
                WHERE product = $1 AND observation_time = $2;
            """, self.product, obs_time)
        else:
            row = await conn.fetchrow("""
                SELECT observation_id, observation_time, product, min_value, max_value,
                       mean_value, spatial_resolution_deg, canonical_file_path, grid_data, attributes
                FROM public.satellite_rainfall_observations
                WHERE product = $1 ORDER BY observation_time DESC LIMIT 1;
            """, self.product)
        await conn.close()

        if not row:
            return None

        # Prefer disk raster if available, otherwise parse JSONB
        tif_path = Path(row["canonical_file_path"])
        if tif_path.exists():
            with rasterio.open(tif_path) as src:
                arr = src.read(1)
                bounds = src.bounds
                nodata = src.nodata
                clean_arr = np.where(arr >= 0.0, arr, np.nan)
        else:
            grid_list = json.loads(row["grid_data"]) if row["grid_data"] else None
            clean_arr = np.array(grid_list, dtype=np.float32) if grid_list else None
            bounds = row["attributes"]["bounds"] if row["attributes"] else None
            nodata = -999.0

        return {
            "observation_id": row["observation_id"],
            "observation_time": row["observation_time"].isoformat(),
            "product": row["product"],
            "bounds": list(bounds) if bounds else None,
            "resolution_deg": row["spatial_resolution_deg"],
            "grid_array": clean_arr,
            "min_rate_mmh": row["min_value"],
            "max_rate_mmh": row["max_value"],
            "mean_rate_mmh": row["mean_value"]
        }

    async def compute_accumulation(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> dict[str, Any]:
        """Compute accumulated rainfall (mm) over a temporal window from half-hourly rates."""
        conn = await self._get_conn()
        rows = await conn.fetch("""
            SELECT observation_id, observation_time, mean_value, max_value,
                   mumbai_core_mean_value, mumbai_core_max_value, canonical_file_path
            FROM public.satellite_rainfall_observations
            WHERE product = $1
              AND observation_time >= $2
              AND observation_time <= $3
            ORDER BY observation_time ASC;
        """, self.product, start_time, end_time)
        await conn.close()

        if not rows:
            return {
                "product": self.product,
                "granules_count": 0,
                "total_accumulation_mm": 0.0,
                "peak_rate_mmh": 0.0,
                "mean_rate_mmh": 0.0,
                "timeseries": []
            }

        # Each half-hourly observation rate (mm/hr) represents ~0.5h of accumulation
        # Accumulation (mm) = sum(rate_mm_hr * dt_hours)
        total_acc_mm = 0.0
        mumbai_acc_mm = 0.0
        peak_rate = 0.0
        ts = []

        for r in rows:
            rate = r["mean_value"] or 0.0
            m_rate = r["mumbai_core_mean_value"] if r["mumbai_core_mean_value"] is not None else rate
            max_r = r["max_value"] or 0.0
            
            # 30-minute interval = 0.5 hours
            step_mm = rate * 0.5
            m_step_mm = m_rate * 0.5
            
            total_acc_mm += step_mm
            mumbai_acc_mm += m_step_mm
            if max_r > peak_rate:
                peak_rate = max_r

            ts.append({
                "time": r["observation_time"].isoformat(),
                "rate_mmh": round(rate, 2),
                "mumbai_rate_mmh": round(m_rate, 2),
                "peak_mmh": round(max_r, 2),
                "step_accumulation_mm": round(m_step_mm, 2)
            })

        return {
            "product": self.product,
            "granules_count": len(rows),
            "window_hours": (end_time - start_time).total_seconds() / 3600.0,
            "wider_accumulation_mm": round(total_acc_mm, 2),
            "mumbai_core_accumulation_mm": round(mumbai_acc_mm, 2),
            "peak_rate_mmh": round(peak_rate, 2),
            "mean_rate_mmh": round(mumbai_acc_mm / max(1.0, len(rows) * 0.5), 2),
            "timeseries": ts
        }

    async def get_antecedent_rainfall(
        self,
        target_time: datetime,
        hours: int = 24,
    ) -> float:
        """Calculate antecedent accumulated rainfall (mm) for N hours prior to target_time."""
        start_time = target_time - timedelta(hours=hours)
        res = await self.compute_accumulation(start_time, target_time)
        return float(res["mumbai_core_accumulation_mm"])
