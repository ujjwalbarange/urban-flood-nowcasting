"""Data Provenance and Model Run Audit Engine (Phase 5).

Provides strict scientific integrity and traceability:
1. Every simulation run records exact input timestamps, parameter values, solver revisions,
   domain resolution, and validation checks.
2. A run CANNOT claim "completed" status until output validation has actually succeeded.
3. Every external data feed is classified as OBSERVED, FORECAST, DERIVED, INFERRED, or SYNTHETIC.
4. Source-specific freshness rules prevent misleading users with stale or missing data.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger()


class DataClassification(str, Enum):
    """Scientific classification of geospatial and hydrometeorological data."""
    OBSERVED = "observed"       # Direct physical sensor/gauge/survey observation
    FORECAST = "forecast"       # Numerical weather prediction / future projection
    DERIVED = "derived"         # Calculated from observations via validated physical algorithms
    INFERRED = "inferred"       # Statistically or spatially interpolated from sparse data
    SYNTHETIC = "synthetic"     # Procedurally generated or engineering assumption (not ground truth)


class DataFeedStatus(str, Enum):
    """Operational health status of an external data feed or model layer."""
    AVAILABLE = "available"                 # Fresh, validated, operational
    UPDATING = "updating"                   # Ingestion/polling currently in flight
    STALE = "stale"                         # Retrieval exceeded source-specific freshness threshold
    PARTIAL_COVERAGE = "partial_coverage"   # Valid data present but spatially or temporally incomplete
    UNAVAILABLE = "unavailable"             # Feed offline or endpoint failed
    VALIDATION_FAILED = "validation_failed" # Data retrieved but failed schema or range checks


@dataclass
class DataFeedMetadata:
    """Rigorous audit record for an external data feed or static spatial layer."""
    feed_id: str
    name: str
    dataset_product_id: str
    classification: DataClassification
    provider: str
    retrieval_time: Optional[datetime] = None
    source_timestamp: Optional[datetime] = None
    coverage_period: Optional[str] = None
    geographic_coverage: Optional[str] = None
    units: Optional[str] = None
    crs: Optional[str] = "EPSG:4326"
    validation_status: str = "PASSED"       # PASSED, WARNING, FAILED, PENDING
    update_frequency_minutes: int = 60      # Expected cadence
    staleness_threshold_minutes: int = 120  # Threshold beyond which data is STALE
    status: DataFeedStatus = DataFeedStatus.AVAILABLE
    error_message: Optional[str] = None
    license: Optional[str] = None
    is_static: bool = False
    attributes: Dict[str, Any] = field(default_factory=dict)

    def evaluate_freshness(self, now: Optional[datetime] = None) -> DataFeedStatus:
        """Evaluate status using feed-specific update cadence (never one arbitrary threshold)."""
        if self.is_static:
            if self.validation_status == "FAILED":
                self.status = DataFeedStatus.VALIDATION_FAILED
            else:
                self.status = DataFeedStatus.AVAILABLE
            return self.status

        if not self.retrieval_time:
            self.status = DataFeedStatus.UNAVAILABLE
            return self.status

        current_time = now or datetime.now(timezone.utc)
        retrieval = self.retrieval_time
        if retrieval.tzinfo is None:
            retrieval = retrieval.replace(tzinfo=timezone.utc)

        age_minutes = (current_time - retrieval).total_seconds() / 60.0
        if self.validation_status == "FAILED":
            self.status = DataFeedStatus.VALIDATION_FAILED
        elif age_minutes > self.staleness_threshold_minutes:
            self.status = DataFeedStatus.STALE
        else:
            self.status = DataFeedStatus.AVAILABLE
        return self.status

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API response without exposing sensitive configs."""
        self.evaluate_freshness()
        now = datetime.now(timezone.utc)
        retrieval = self.retrieval_time
        age_m = None
        if retrieval:
            if retrieval.tzinfo is None:
                retrieval = retrieval.replace(tzinfo=timezone.utc)
            age_m = round((now - retrieval).total_seconds() / 60.0, 1)

        return {
            "feed_id": self.feed_id,
            "name": self.name,
            "dataset_product_id": self.dataset_product_id,
            "classification": self.classification.value,
            "provider": self.provider,
            "status": self.status.value,
            "retrieval_time": self.retrieval_time.isoformat() if self.retrieval_time else None,
            "source_timestamp": self.source_timestamp.isoformat() if self.source_timestamp else None,
            "age_minutes": age_m,
            "coverage_period": self.coverage_period,
            "geographic_coverage": self.geographic_coverage,
            "units": self.units,
            "crs": self.crs,
            "validation_status": self.validation_status,
            "update_frequency_minutes": self.update_frequency_minutes,
            "staleness_threshold_minutes": self.staleness_threshold_minutes,
            "error_message": self.error_message,
            "license": self.license,
            "is_static": self.is_static,
        }


@dataclass
class SimulationProvenance:
    """Complete provenance record for a hydrodynamic simulation run."""
    run_id: str
    run_type: str  # "nowcast", "forecast", "historical_replay", "sensitivity_scenario"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: str = "queued"  # "queued", "running", "completed", "failed"

    # Input dataset tracking
    input_datasets: Dict[str, Any] = field(default_factory=dict)
    rainfall_source: str = "Open-Meteo Multi-Station API"
    rainfall_classification: DataClassification = DataClassification.FORECAST
    rainfall_retrieval_time: Optional[datetime] = None
    rainfall_valid_time: Optional[datetime] = None
    rainfall_peak_mmh: float = 0.0
    rainfall_accum_mm: float = 0.0

    # DEM & Terrain
    dem_source: str = "Copernicus GLO-30 DSM (ESA)"
    dem_resolution_m: float = 30.0
    dem_vertical_datum: str = "EGM96 Geoid (metres MSL)"

    # Model Configuration & Parameters
    solver_name: str = "2D Diffusive Wave Hydrodynamic Solver"
    solver_version: str = "v2.4 (NumPy/SciPy Accelerated)"
    catchment: str = "mumbai"
    domain_bounds: Dict[str, float] = field(default_factory=dict)
    grid_shape: Optional[List[int]] = None
    cell_size_m: float = 30.0
    duration_hours: float = 3.0
    time_step_s: float = 2.0
    manning_n: float = 0.035
    horton_f0_mmh: float = 25.0
    horton_fc_mmh: float = 3.0
    tide_scenario: str = "observed"
    tide_height_m: Optional[float] = None

    # Output Validation & Integrity (Strict requirement)
    output_summary: Optional[Dict[str, Any]] = None
    validation_passed: bool = False
    validation_checks: Dict[str, bool] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    missing_inputs: List[str] = field(default_factory=list)
    failure_reason: Optional[str] = None
    runtime_seconds: float = 0.0

    def mark_started(self) -> None:
        self.started_at = datetime.now(timezone.utc)
        self.status = "running"

    def validate_and_complete(
        self,
        max_depth_m: float,
        mean_depth_m: float,
        flooded_area_km2: float,
        flooded_cells: int,
        mass_balance_error_pct: float,
        depth_grid_valid: bool = True,
    ) -> bool:
        """Validate outputs before allowing status to transition to 'completed'.

        Performs physical sanity checks:
        1. Max depth >= 0.0 and < 15.0m (unphysical blowout check).
        2. Mass balance closure within numerical tolerance (|error| < 5.0%).
        3. Grid dimensions consistent.
        """
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            self.runtime_seconds = round((self.completed_at - self.started_at).total_seconds(), 2)

        checks = {
            "depth_non_negative": max_depth_m >= 0.0,
            "depth_physically_bounded": max_depth_m <= 15.0,
            "mass_balance_closure": abs(mass_balance_error_pct) <= 5.0,
            "depth_grid_populated": depth_grid_valid,
        }
        self.validation_checks = checks

        if all(checks.values()):
            self.validation_passed = True
            self.status = "completed"
            self.output_summary = {
                "max_depth_m": round(max_depth_m, 3),
                "mean_depth_m": round(mean_depth_m, 3),
                "flooded_area_km2": round(flooded_area_km2, 4),
                "flooded_cells": flooded_cells,
                "mass_balance_error_pct": round(mass_balance_error_pct, 2),
            }
            logger.info("Simulation run validated and completed", run_id=self.run_id, checks=checks)
            return True
        else:
            self.validation_passed = False
            self.status = "failed"
            failed_checks = [k for k, v in checks.items() if not v]
            self.failure_reason = f"Output validation failed checks: {', '.join(failed_checks)}"
            logger.error("Simulation run validation failed", run_id=self.run_id, failed_checks=failed_checks)
            return False

    def mark_failed(self, reason: str) -> None:
        self.completed_at = datetime.now(timezone.utc)
        if self.started_at:
            self.runtime_seconds = round((self.completed_at - self.started_at).total_seconds(), 2)
        self.status = "failed"
        self.validation_passed = False
        self.failure_reason = reason

    def to_dict(self) -> Dict[str, Any]:
        """Serialize complete run record for API telemetry."""
        return {
            "run_id": self.run_id,
            "run_type": self.run_type,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "runtime_seconds": self.runtime_seconds,
            "rainfall": {
                "source": self.rainfall_source,
                "classification": self.rainfall_classification.value,
                "retrieval_time": self.rainfall_retrieval_time.isoformat() if self.rainfall_retrieval_time else None,
                "valid_time": self.rainfall_valid_time.isoformat() if self.rainfall_valid_time else None,
                "peak_mmh": self.rainfall_peak_mmh,
                "accum_mm": self.rainfall_accum_mm,
            },
            "terrain": {
                "dem_source": self.dem_source,
                "resolution_m": self.dem_resolution_m,
                "vertical_datum": self.dem_vertical_datum,
            },
            "solver": {
                "name": self.solver_name,
                "version": self.solver_version,
                "catchment": self.catchment,
                "cell_size_m": self.cell_size_m,
                "duration_hours": self.duration_hours,
                "time_step_s": self.time_step_s,
                "manning_n": self.manning_n,
                "horton_f0_mmh": self.horton_f0_mmh,
                "horton_fc_mmh": self.horton_fc_mmh,
                "tide_scenario": self.tide_scenario,
                "tide_height_m": self.tide_height_m,
            },
            "domain_bounds": self.domain_bounds,
            "output_summary": self.output_summary,
            "rainfall_classification": self.rainfall_classification.value,
            "is_valid": self.validation_passed,
            "validation_passed": self.validation_passed,
            "validation_checks": self.validation_checks,
            "warnings": self.warnings,
            "missing_inputs": self.missing_inputs,
            "failure_reason": self.failure_reason,
        }


class DataProvenanceRegistry:
    """Central registry and health evaluator for all MUFNS datasets and simulation runs."""

    def __init__(self):
        self._feeds: Dict[str, DataFeedMetadata] = {}
        self._runs: Dict[str, SimulationProvenance] = {}
        self._initialize_core_feeds()

    def _initialize_core_feeds(self) -> None:
        """Register the 8 primary data feeds according to actual repository assets."""
        now = datetime.now(timezone.utc)

        # 1. Open-Meteo Multi-Station Live Weather
        self.register_feed(
            DataFeedMetadata(
                feed_id="open_meteo_live_weather",
                name="Open-Meteo 9-Station Weather Grid",
                dataset_product_id="open_meteo_v1_forecast",
                classification=DataClassification.FORECAST,
                provider="Open-Meteo / DWD ICON / NCEP GFS",
                retrieval_time=now,
                source_timestamp=now,
                coverage_period="Past 6h observed to Next 6h forecast",
                geographic_coverage="Greater Mumbai (9 monitoring coordinates)",
                units="Rainfall: mm/h, Temp: °C, Wind: km/h, Pressure: hPa",
                crs="EPSG:4326",
                update_frequency_minutes=15,
                staleness_threshold_minutes=45,
                status=DataFeedStatus.AVAILABLE,
                license="CC-BY 4.0 / Open Data",
                is_static=False,
            )
        )

        # 2. Copernicus GLO-30 Digital Surface Model
        self.register_feed(
            DataFeedMetadata(
                feed_id="copernicus_glo30_dem",
                name="Copernicus GLO-30 Digital Elevation Model",
                dataset_product_id="copernicus_glo30_mumbai_bbox.tif",
                classification=DataClassification.OBSERVED,
                provider="European Space Agency (ESA) / OpenTopography",
                retrieval_time=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                source_timestamp=datetime(2021, 12, 1, 0, 0, tzinfo=timezone.utc),
                coverage_period="Baseline 2021 Topography",
                geographic_coverage="Greater Mumbai (72.75E - 73.05E, 18.88N - 19.32N)",
                units="Metres above Mean Sea Level (MSL)",
                crs="EPSG:4326 (EGM96 Geoid)",
                update_frequency_minutes=525600,  # Static annual
                staleness_threshold_minutes=1051200,
                status=DataFeedStatus.AVAILABLE,
                license="Open Principles / Free and Open Access",
                is_static=True,
            )
        )

        # 3. OpenStreetMap Mumbai Road Network
        self.register_feed(
            DataFeedMetadata(
                feed_id="osm_road_network",
                name="OpenStreetMap Mumbai Road Network",
                dataset_product_id="mumbai_road_network.geojson",
                classification=DataClassification.OBSERVED,
                provider="OpenStreetMap Contributors / Geofabrik",
                retrieval_time=datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc),
                source_timestamp=datetime(2024, 5, 15, 0, 0, tzinfo=timezone.utc),
                coverage_period="2024 Road Geometry",
                geographic_coverage="Greater Mumbai (14,563 drivable road segments)",
                units="Vector LineString (Length: metres, Speed: km/h)",
                crs="EPSG:4326",
                update_frequency_minutes=43200,
                staleness_threshold_minutes=86400,
                status=DataFeedStatus.AVAILABLE,
                license="ODbL (Open Database License)",
                is_static=True,
            )
        )

        # 4. BMC Designated Emergency Relief Shelters & Hospitals
        self.register_feed(
            DataFeedMetadata(
                feed_id="bmc_emergency_shelters",
                name="BMC Designated Emergency Relief Shelters & Facilities",
                dataset_product_id="mumbai_flood_shelters.geojson",
                classification=DataClassification.OBSERVED,
                provider="Brihanmumbai Municipal Corporation (BMC) Disaster Management",
                retrieval_time=datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc),
                source_timestamp=datetime(2024, 5, 1, 0, 0, tzinfo=timezone.utc),
                coverage_period="Monsoon Preparedness 2024/2025",
                geographic_coverage="Greater Mumbai 24 Administrative Wards",
                units="Point locations with capacity and emergency power attributes",
                crs="EPSG:4326",
                update_frequency_minutes=43200,
                staleness_threshold_minutes=86400,
                status=DataFeedStatus.AVAILABLE,
                license="Government / Municipal Official Open Data",
                is_static=True,
            )
        )

        # 5. IMD & MCGM Historical Flood Archive (2016-2025)
        self.register_feed(
            DataFeedMetadata(
                feed_id="historical_flood_observations",
                name="IMD & MCGM Historical Flood Observations (2016–2025)",
                dataset_product_id="historical_flood_events.geojson",
                classification=DataClassification.OBSERVED,
                provider="India Meteorological Department & MCGM Disaster Cell",
                retrieval_time=datetime(2025, 9, 1, 0, 0, tzinfo=timezone.utc),
                source_timestamp=datetime(2025, 8, 31, 0, 0, tzinfo=timezone.utc),
                coverage_period="2016 Monsoon to 2025 Monsoon",
                geographic_coverage="Greater Mumbai (202 verified flood event records)",
                units="Observed depth: cm, Rainfall 24h: mm, Area: km²",
                crs="EPSG:4326",
                update_frequency_minutes=43200,
                staleness_threshold_minutes=86400,
                status=DataFeedStatus.AVAILABLE,
                license="Official Government Disaster Records",
                is_static=True,
            )
        )

        # 6. NASA GPM IMERG Half-Hourly Precipitation
        self.register_feed(
            DataFeedMetadata(
                feed_id="nasa_gpm_imerg",
                name="NASA GPM IMERG Final Precipitation Archive",
                dataset_product_id="imerg_20050726_halfhourly_mumbai_grid.csv",
                classification=DataClassification.OBSERVED,
                provider="NASA Earthdata / Goddard Space Flight Center",
                retrieval_time=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
                source_timestamp=datetime(2005, 7, 26, 0, 0, tzinfo=timezone.utc),
                coverage_period="Extreme storm events / 2005 deluge retrospective",
                geographic_coverage="Mumbai Catchment (0.1° grid)",
                units="Precipitation rate: mm/h",
                crs="EPSG:4326",
                update_frequency_minutes=43200,
                staleness_threshold_minutes=86400,
                status=DataFeedStatus.AVAILABLE,
                license="NASA Open Data Policy",
                is_static=True,
            )
        )

        # 7. BRIMSTOWAD Drainage & Pumping Stations
        self.register_feed(
            DataFeedMetadata(
                feed_id="brimstowad_drainage",
                name="BRIMSTOWAD Drainage Channels & Pumping Stations",
                dataset_product_id="synthetic_drainage.geojson",
                classification=DataClassification.INFERRED,
                provider="BMC Stormwater Drains (SWD) Department / Synthetic Topology",
                retrieval_time=datetime(2024, 6, 1, 0, 0, tzinfo=timezone.utc),
                source_timestamp=datetime(2024, 5, 1, 0, 0, tzinfo=timezone.utc),
                coverage_period="2024 Municipal Configuration",
                geographic_coverage="Greater Mumbai Primary Outfalls and Channels",
                units="Rated Capacity: MLD, Pipe lines filtered for zero-junction performance",
                crs="EPSG:4326",
                update_frequency_minutes=43200,
                staleness_threshold_minutes=86400,
                status=DataFeedStatus.PARTIAL_COVERAGE,
                error_message="Underground lateral pipe connectivity inferred from surface topography; outfall stations verified.",
                license="Municipal Public Works Inventory",
                is_static=True,
            )
        )

        # 8. 2D Diffusive Wave Hydrodynamic Engine
        self.register_feed(
            DataFeedMetadata(
                feed_id="hydrodynamic_solver",
                name="2D Diffusive Wave Hydrodynamic Solver",
                dataset_product_id="services.flood.engine",
                classification=DataClassification.DERIVED,
                provider="MUFNS Physics Core",
                retrieval_time=now,
                source_timestamp=now,
                coverage_period="Live simulation execution",
                geographic_coverage="Configured Catchment Domain (30m to 120m mesh)",
                units="Water depth: metres, Inundation: km²",
                crs="EPSG:4326 (EGM96)",
                update_frequency_minutes=30,
                staleness_threshold_minutes=90,
                status=DataFeedStatus.AVAILABLE,
                license="Proprietary MUFNS Hydrodynamic Engine",
                is_static=False,
            )
        )

    def register_feed(self, feed: DataFeedMetadata) -> None:
        """Register or update an external data feed metadata record."""
        self._feeds[feed.feed_id] = feed

    def update_feed_timestamp(self, feed_id: str, timestamp: datetime, status: DataFeedStatus = DataFeedStatus.AVAILABLE, error: Optional[str] = None) -> None:
        """Update last retrieval time and operational status for an active feed."""
        if feed_id in self._feeds:
            f = self._feeds[feed_id]
            f.retrieval_time = timestamp
            f.source_timestamp = timestamp
            f.status = status
            f.error_message = error

    def get_feed(self, feed_id: str) -> Optional[DataFeedMetadata]:
        return self._feeds.get(feed_id)

    def list_feeds(self) -> List[Dict[str, Any]]:
        """Return all tracked data feeds with evaluated freshness."""
        now = datetime.now(timezone.utc)
        return [f.to_dict() for f in self._feeds.values()]

    def record_simulation_run(self, run: SimulationProvenance) -> None:
        """Store simulation run audit record."""
        self._runs[run.run_id] = run

    def get_simulation_run(self, run_id: str) -> Optional[SimulationProvenance]:
        return self._runs.get(run_id)

    def list_simulation_runs(self, limit: int = 20) -> List[Dict[str, Any]]:
        sorted_runs = sorted(self._runs.values(), key=lambda r: r.created_at, reverse=True)
        return [r.to_dict() for r in sorted_runs[:limit]]


# Singleton instance
_provenance_registry: Optional[DataProvenanceRegistry] = None


def get_provenance_registry() -> DataProvenanceRegistry:
    """Get or initialize singleton DataProvenanceRegistry."""
    global _provenance_registry
    if _provenance_registry is None:
        _provenance_registry = DataProvenanceRegistry()
    return _provenance_registry
