"""Multi-Sensor Rainfall Fusion Engine for Mumbai Urban Flood Nowcasting.

Provides genuine multi-source rainfall fusion, not just pass-through:
1. HEM_ONLY       — Primary INSAT-3DR Hydro-Estimator precipitation product
2. IMC_ONLY       — Secondary/Validation INSAT-3DR IMAGER precipitation retrieval
3. GPM_ONLY       — NASA GPM IMERG gridded satellite precipitation
4. GPM_HEM        — Weighted blend of GPM + INSAT-3DR HEM (temporal alignment + weighted mean)
5. GPM_IMC        — Weighted blend of GPM + INSAT-3DR IMC (temporal alignment + weighted mean)
6. FULL_FUSION    — Multi-source: GPM + HEM + IMC + surface gauge calibration

Blending methodology:
- Temporal alignment: GPM (30-min) and INSAT (30-min) are matched to nearest timestamp
- Where both products have valid data: weighted mean (default: HEM/IMC=0.6, GPM=0.4)
- Where only one product has data: use available product with reduced confidence
- AWS gauge bias correction: multiplicative adjustment where gauge data overlaps

Strictly adheres to:
- No automatic averaging of HEM and IMC unless explicitly requested by mode.
- Preserves discrete satellite observations and authentic timestamps.
- Zero fabrication of unobserved dates.
- Records all fusion metadata for provenance.
"""

from __future__ import annotations

import os
import ssl
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional, Dict, List
import asyncpg
import numpy as np
from dotenv import load_dotenv

load_dotenv()

from packages.contracts.rainfall import RainfallObservation, RainfallSpatialType
from packages.contracts.provenance import DataSource, DataQuality, DataOrigin, Provenance
from services.rainfall.insat_service import INSAT3DRProvider
from services.rainfall.imerg import IMERGProvider


class RainfallFusionMode(str, Enum):
    """Allowed experiment-driven rainfall fusion modes."""
    HEM_ONLY = "hem_only"                   # Primary INSAT-3DR Hydro-Estimator
    IMC_ONLY = "imc_only"                   # Secondary/Validation INSAT-3DR IMAGER
    GPM_ONLY = "gpm_only"                   # NASA GPM IMERG V06B/V07B
    GPM_HEM = "gpm_hem"                     # Dual Satellite Blend: NASA GPM + INSAT-3DR HEM
    GPM_IMC = "gpm_imc"                     # Dual Satellite Blend: NASA GPM + INSAT-3DR IMC
    FULL_FUSION = "full_fusion"             # Multi-sensor: GPM + HEM + IMC + Surface Gauges


class RainfallFusionEngine:
    """Orchestrates rainfall data retrieval and genuine multi-source fusion."""

    # Default blend weights (can be overridden per call)
    DEFAULT_INSAT_WEIGHT = 0.6   # INSAT has higher temporal sampling (~30min geostationary)
    DEFAULT_GPM_WEIGHT = 0.4     # GPM has better calibration but coarser spatial resolution
    TEMPORAL_MATCH_TOLERANCE_MIN = 20  # Max minutes difference for timestamp matching

    def __init__(
        self,
        mode: RainfallFusionMode = RainfallFusionMode.HEM_ONLY,
        db_url: Optional[str] = None,
        insat_weight: float = 0.6,
        gpm_weight: float = 0.4,
    ):
        self.mode = mode
        raw_url = db_url or os.environ.get("DATABASE_URL", "")
        self.clean_url = raw_url.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]

        self.ssl_ctx = ssl.create_default_context()
        self.ssl_ctx.check_hostname = False
        self.ssl_ctx.verify_mode = ssl.CERT_NONE

        self.insat_weight = insat_weight
        self.gpm_weight = gpm_weight

        # Sub-providers
        self.hem_provider = INSAT3DRProvider(product="HEM", db_url=self.clean_url)
        self.imc_provider = INSAT3DRProvider(product="IMC", db_url=self.clean_url)
        self.gpm_provider = IMERGProvider()

    async def _get_conn(self) -> asyncpg.Connection:
        return await asyncpg.connect(self.clean_url, ssl=self.ssl_ctx)

    async def _fetch_gpm_timeseries(
        self, conn: asyncpg.Connection, start_time: datetime, end_time: datetime
    ) -> List[dict]:
        """Fetch GPM IMERG timeseries from PostGIS."""
        rows = await conn.fetch("""
            SELECT timestamp, avg(precipitation_mm_hr) as mean_rate,
                   max(precipitation_mm_hr) as max_rate
            FROM public.rainfall_satellite
            WHERE timestamp >= $1 AND timestamp <= $2
            GROUP BY timestamp ORDER BY timestamp ASC;
        """, start_time, end_time)
        return [
            {
                "time": r["timestamp"],
                "rate_mmh": float(r["mean_rate"] or 0.0),
                "peak_mmh": float(r["max_rate"] or 0.0),
                "source": "GPM_IMERG",
            }
            for r in rows
        ]

    async def _fetch_gauge_timeseries(
        self, conn: asyncpg.Connection, start_time: datetime, end_time: datetime
    ) -> List[dict]:
        """Fetch ground gauge observations from PostGIS."""
        rows = await conn.fetch("""
            SELECT observed_at, station_name, value, unit
            FROM public.rainfall_observations
            WHERE observed_at >= $1 AND observed_at <= $2
              AND variable = 'rainfall' OR unit IN ('mm', 'mm/hr')
            ORDER BY observed_at ASC;
        """, start_time, end_time)
        return [
            {
                "time": r["observed_at"],
                "rate_mmh": float(r["value"] or 0.0),
                "station": r["station_name"],
                "source": "AWS_GAUGE",
            }
            for r in rows
        ]

    def _temporal_align_and_blend(
        self,
        primary_ts: List[dict],
        secondary_ts: List[dict],
        w_primary: float,
        w_secondary: float,
        primary_label: str,
        secondary_label: str,
    ) -> List[dict]:
        """Align two timeseries by timestamp and compute weighted blend.

        For each primary timestep:
        - Find the closest secondary timestep within TEMPORAL_MATCH_TOLERANCE_MIN
        - If matched: blended_rate = w_primary * primary + w_secondary * secondary
        - If not matched: use primary rate with reduced confidence

        Returns: list of blended timestep dicts with full provenance
        """
        tolerance = timedelta(minutes=self.TEMPORAL_MATCH_TOLERANCE_MIN)
        blended = []
        matched_count = 0
        unmatched_count = 0

        # Build secondary lookup (timestamp -> rate)
        sec_lookup = {}
        for s in secondary_ts:
            sec_lookup[s["time"]] = s

        for p in primary_ts:
            p_time = p["time"]
            p_rate = p["rate_mmh"]

            # Find closest secondary within tolerance
            best_match = None
            best_delta = tolerance
            for s_time, s_data in sec_lookup.items():
                delta = abs(p_time - s_time) if isinstance(p_time, datetime) and isinstance(s_time, datetime) else tolerance
                if delta <= best_delta:
                    best_delta = delta
                    best_match = s_data

            if best_match is not None:
                s_rate = best_match["rate_mmh"]
                blended_rate = w_primary * p_rate + w_secondary * s_rate
                matched_count += 1
                blend_method = f"weighted_mean({primary_label}={w_primary:.1f},{secondary_label}={w_secondary:.1f})"
                confidence = "high"
                sources = [primary_label, secondary_label]
            else:
                blended_rate = p_rate
                unmatched_count += 1
                blend_method = f"single_source({primary_label})"
                confidence = "medium"
                sources = [primary_label]

            blended.append({
                "time": p_time.isoformat() if isinstance(p_time, datetime) else str(p_time),
                "rate_mmh": round(blended_rate, 2),
                "peak_mmh": round(p.get("peak_mmh", p_rate), 2),
                "step_accumulation_mm": round(blended_rate * 0.5, 2),  # 30-min step
                "blend_method": blend_method,
                "confidence": confidence,
                "sources": sources,
            })

        return blended, matched_count, unmatched_count

    def _apply_gauge_bias_correction(
        self,
        blended_ts: List[dict],
        gauge_ts: List[dict],
    ) -> tuple[List[dict], dict]:
        """Apply multiplicative bias correction using gauge observations.

        For each gauge observation, find the nearest blended timestep and compute
        a local bias ratio. The overall correction factor is the median of these ratios.

        Returns: (corrected_timeseries, correction_metadata)
        """
        if not gauge_ts:
            return blended_ts, {"correction_applied": False, "reason": "no_gauge_data"}

        tolerance = timedelta(minutes=30)
        ratios = []

        for g in gauge_ts:
            g_time = g["time"]
            g_rate = g["rate_mmh"]

            if g_rate < 0.1:  # Skip near-zero gauge readings
                continue

            # Find closest blended timestep
            best_match = None
            best_delta = tolerance
            for b in blended_ts:
                try:
                    b_time = datetime.fromisoformat(b["time"]) if isinstance(b["time"], str) else b["time"]
                except (ValueError, TypeError):
                    continue
                delta = abs(g_time - b_time) if isinstance(g_time, datetime) else tolerance
                if delta <= best_delta:
                    best_delta = delta
                    best_match = b

            if best_match and best_match["rate_mmh"] > 0.1:
                ratio = g_rate / best_match["rate_mmh"]
                if 0.2 < ratio < 5.0:  # Reject extreme ratios
                    ratios.append(ratio)

        if not ratios:
            return blended_ts, {
                "correction_applied": False,
                "reason": "no_valid_gauge_satellite_pairs",
                "gauge_records": len(gauge_ts),
            }

        # Median bias correction factor
        correction_factor = float(np.median(ratios))

        corrected = []
        for b in blended_ts:
            corrected_rate = b["rate_mmh"] * correction_factor
            entry = dict(b)
            entry["rate_mmh"] = round(corrected_rate, 2)
            entry["step_accumulation_mm"] = round(corrected_rate * 0.5, 2)
            entry["bias_corrected"] = True
            corrected.append(entry)

        correction_meta = {
            "correction_applied": True,
            "method": "multiplicative_median_bias",
            "correction_factor": round(correction_factor, 4),
            "gauge_satellite_pairs": len(ratios),
            "gauge_records_total": len(gauge_ts),
            "ratio_min": round(min(ratios), 4),
            "ratio_max": round(max(ratios), 4),
            "ratio_median": round(correction_factor, 4),
        }

        return corrected, correction_meta

    async def get_rainfall_forcing(
        self,
        start_time: datetime,
        end_time: datetime,
        latitude: float = 19.076,
        longitude: float = 72.877,
    ) -> Dict[str, Any]:
        """Fetch and fuse rainfall forcing according to selected mode.

        Returns structured dictionary with full provenance for every fusion step.
        """
        conn = await self._get_conn()

        result = {
            "mode": self.mode.value,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "sources_used": [],
            "timeseries": [],
            "cumulative_mm": 0.0,
            "peak_rate_mmh": 0.0,
            "fusion_metadata": {},
        }

        try:
            # --- Single-source modes ---
            if self.mode == RainfallFusionMode.HEM_ONLY:
                result["sources_used"] = ["ISRO MOSDAC INSAT-3DR (HEM L2B)"]
                acc = await self.hem_provider.compute_accumulation(start_time, end_time)
                result["cumulative_mm"] = acc["mumbai_core_accumulation_mm"]
                result["peak_rate_mmh"] = acc["peak_rate_mmh"]
                result["timeseries"] = acc["timeseries"]
                result["fusion_metadata"] = {
                    "method": "single_source",
                    "primary": "HEM",
                    "granules": acc["granules_count"],
                }

            elif self.mode == RainfallFusionMode.IMC_ONLY:
                result["sources_used"] = ["ISRO MOSDAC INSAT-3DR (IMC L2B)"]
                acc = await self.imc_provider.compute_accumulation(start_time, end_time)
                result["cumulative_mm"] = acc["mumbai_core_accumulation_mm"]
                result["peak_rate_mmh"] = acc["peak_rate_mmh"]
                result["timeseries"] = acc["timeseries"]
                result["fusion_metadata"] = {
                    "method": "single_source",
                    "primary": "IMC",
                    "granules": acc["granules_count"],
                }

            elif self.mode == RainfallFusionMode.GPM_ONLY:
                result["sources_used"] = ["NASA GPM IMERG (V06B/V07B)"]
                gpm_ts = await self._fetch_gpm_timeseries(conn, start_time, end_time)
                cum = sum(g["rate_mmh"] * 0.5 for g in gpm_ts)
                peak = max((g["peak_mmh"] for g in gpm_ts), default=0.0)
                result["cumulative_mm"] = round(cum, 2)
                result["peak_rate_mmh"] = round(peak, 2)
                result["timeseries"] = [
                    {
                        "time": g["time"].isoformat() if isinstance(g["time"], datetime) else str(g["time"]),
                        "rate_mmh": round(g["rate_mmh"], 2),
                        "peak_mmh": round(g["peak_mmh"], 2),
                        "step_accumulation_mm": round(g["rate_mmh"] * 0.5, 2),
                    }
                    for g in gpm_ts
                ]
                result["fusion_metadata"] = {
                    "method": "single_source",
                    "primary": "GPM_IMERG",
                    "records": len(gpm_ts),
                }

            # --- Dual-source blend modes ---
            elif self.mode == RainfallFusionMode.GPM_HEM:
                result["sources_used"] = [
                    "ISRO MOSDAC INSAT-3DR (HEM High-Frequency)",
                    "NASA GPM IMERG (Calibrated Gridded)",
                ]

                # Fetch both timeseries
                hem_acc = await self.hem_provider.compute_accumulation(start_time, end_time)
                gpm_ts = await self._fetch_gpm_timeseries(conn, start_time, end_time)

                # Convert HEM timeseries to common format
                hem_ts = [
                    {
                        "time": datetime.fromisoformat(t["time"]) if isinstance(t["time"], str) else t["time"],
                        "rate_mmh": t["mumbai_rate_mmh"],
                        "peak_mmh": t["peak_mmh"],
                        "source": "HEM",
                    }
                    for t in hem_acc["timeseries"]
                ]

                # Blend
                blended, matched, unmatched = self._temporal_align_and_blend(
                    primary_ts=hem_ts,
                    secondary_ts=gpm_ts,
                    w_primary=self.insat_weight,
                    w_secondary=self.gpm_weight,
                    primary_label="HEM",
                    secondary_label="GPM",
                )

                cum = sum(b["step_accumulation_mm"] for b in blended)
                peak = max((b["peak_mmh"] for b in blended), default=0.0)
                result["timeseries"] = blended
                result["cumulative_mm"] = round(cum, 2)
                result["peak_rate_mmh"] = round(peak, 2)
                result["fusion_metadata"] = {
                    "method": "weighted_temporal_blend",
                    "primary": "HEM",
                    "secondary": "GPM_IMERG",
                    "weights": {"HEM": self.insat_weight, "GPM": self.gpm_weight},
                    "temporal_match_tolerance_min": self.TEMPORAL_MATCH_TOLERANCE_MIN,
                    "matched_timesteps": matched,
                    "unmatched_timesteps": unmatched,
                    "hem_granules": hem_acc["granules_count"],
                    "gpm_records": len(gpm_ts),
                }

            elif self.mode == RainfallFusionMode.GPM_IMC:
                result["sources_used"] = [
                    "ISRO MOSDAC INSAT-3DR (IMC Retrieval)",
                    "NASA GPM IMERG (Calibrated Gridded)",
                ]

                imc_acc = await self.imc_provider.compute_accumulation(start_time, end_time)
                gpm_ts = await self._fetch_gpm_timeseries(conn, start_time, end_time)

                imc_ts = [
                    {
                        "time": datetime.fromisoformat(t["time"]) if isinstance(t["time"], str) else t["time"],
                        "rate_mmh": t["mumbai_rate_mmh"],
                        "peak_mmh": t["peak_mmh"],
                        "source": "IMC",
                    }
                    for t in imc_acc["timeseries"]
                ]

                blended, matched, unmatched = self._temporal_align_and_blend(
                    primary_ts=imc_ts,
                    secondary_ts=gpm_ts,
                    w_primary=self.insat_weight,
                    w_secondary=self.gpm_weight,
                    primary_label="IMC",
                    secondary_label="GPM",
                )

                cum = sum(b["step_accumulation_mm"] for b in blended)
                peak = max((b["peak_mmh"] for b in blended), default=0.0)
                result["timeseries"] = blended
                result["cumulative_mm"] = round(cum, 2)
                result["peak_rate_mmh"] = round(peak, 2)
                result["fusion_metadata"] = {
                    "method": "weighted_temporal_blend",
                    "primary": "IMC",
                    "secondary": "GPM_IMERG",
                    "weights": {"IMC": self.insat_weight, "GPM": self.gpm_weight},
                    "matched_timesteps": matched,
                    "unmatched_timesteps": unmatched,
                    "imc_granules": imc_acc["granules_count"],
                    "gpm_records": len(gpm_ts),
                }

            # --- Full multi-source fusion ---
            elif self.mode == RainfallFusionMode.FULL_FUSION:
                result["sources_used"] = [
                    "ISRO MOSDAC INSAT-3DR (HEM Primary)",
                    "ISRO MOSDAC INSAT-3DR (IMC Retrieval)",
                    "NASA GPM IMERG",
                    "Ground Surface Rain Gauges",
                ]

                # Fetch all sources
                hem_acc = await self.hem_provider.compute_accumulation(start_time, end_time)
                imc_acc = await self.imc_provider.compute_accumulation(start_time, end_time)
                gpm_ts = await self._fetch_gpm_timeseries(conn, start_time, end_time)
                gauge_ts = await self._fetch_gauge_timeseries(conn, start_time, end_time)

                # Step 1: Blend HEM + GPM as primary fusion
                hem_ts = [
                    {
                        "time": datetime.fromisoformat(t["time"]) if isinstance(t["time"], str) else t["time"],
                        "rate_mmh": t["mumbai_rate_mmh"],
                        "peak_mmh": t["peak_mmh"],
                        "source": "HEM",
                    }
                    for t in hem_acc["timeseries"]
                ]

                blended, matched_gpm, unmatched_gpm = self._temporal_align_and_blend(
                    primary_ts=hem_ts,
                    secondary_ts=gpm_ts,
                    w_primary=0.5,
                    w_secondary=0.3,
                    primary_label="HEM",
                    secondary_label="GPM",
                )

                # Step 2: Blend with IMC (lower weight, validation role)
                imc_ts_aligned = [
                    {
                        "time": datetime.fromisoformat(t["time"]) if isinstance(t["time"], str) else t["time"],
                        "rate_mmh": t["mumbai_rate_mmh"],
                        "peak_mmh": t["peak_mmh"],
                        "source": "IMC",
                    }
                    for t in imc_acc["timeseries"]
                ]

                # Add IMC contribution where available
                imc_lookup = {}
                for i in imc_ts_aligned:
                    imc_lookup[i["time"]] = i

                for b in blended:
                    try:
                        b_time = datetime.fromisoformat(b["time"]) if isinstance(b["time"], str) else b["time"]
                    except (ValueError, TypeError):
                        continue

                    # Find closest IMC
                    best_imc = None
                    best_delta = timedelta(minutes=self.TEMPORAL_MATCH_TOLERANCE_MIN)
                    for i_time, i_data in imc_lookup.items():
                        delta = abs(b_time - i_time) if isinstance(i_time, datetime) else best_delta
                        if delta <= best_delta:
                            best_delta = delta
                            best_imc = i_data

                    if best_imc:
                        # Blend in IMC with remaining weight (0.2)
                        current_rate = b["rate_mmh"]
                        imc_rate = best_imc["rate_mmh"]
                        fused_rate = current_rate * 0.8 + imc_rate * 0.2
                        b["rate_mmh"] = round(fused_rate, 2)
                        b["step_accumulation_mm"] = round(fused_rate * 0.5, 2)
                        b["sources"] = b.get("sources", []) + ["IMC"]
                        b["blend_method"] = "full_fusion(HEM=0.5,GPM=0.3,IMC=0.2)"

                # Step 3: Apply gauge bias correction
                blended, correction_meta = self._apply_gauge_bias_correction(blended, gauge_ts)

                cum = sum(b["step_accumulation_mm"] for b in blended)
                peak = max((b["peak_mmh"] for b in blended), default=0.0)
                result["timeseries"] = blended
                result["cumulative_mm"] = round(cum, 2)
                result["peak_rate_mmh"] = round(peak, 2)
                result["fusion_metadata"] = {
                    "method": "full_multi_source_fusion",
                    "weights": {"HEM": 0.5, "GPM": 0.3, "IMC": 0.2},
                    "gauge_bias_correction": correction_meta,
                    "hem_granules": hem_acc["granules_count"],
                    "imc_granules": imc_acc["granules_count"],
                    "gpm_records": len(gpm_ts),
                    "gauge_records": len(gauge_ts),
                    "matched_gpm_timesteps": matched_gpm,
                }

        finally:
            await conn.close()

        return result
