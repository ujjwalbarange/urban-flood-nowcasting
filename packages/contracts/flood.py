"""Flood state and simulation contracts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SimulationMode(str, Enum):
    """Operating mode of a simulation run."""

    LIVE = "live"               # Real-time with current data
    HISTORICAL = "historical"   # Replay of a past event
    SCENARIO = "scenario"       # What-if analysis with custom parameters


class SimulationStatus(str, Enum):
    """Lifecycle status of a simulation run."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MassBalance(BaseModel):
    """Mass balance ledger for a simulation.

    The fundamental identity:
        rain_in - infiltration - drainage_outfall - boundary_outflow = ΔS_surface + ΔS_drainage
    
    If closure_error_pct > 1%, something is wrong with the physics.
    """

    total_rainfall_m3: float = 0.0
    total_infiltration_m3: float = 0.0
    total_drainage_exchange_m3: float = 0.0
    total_boundary_outflow_m3: float = 0.0
    initial_surface_volume_m3: float = 0.0
    final_surface_volume_m3: float = 0.0
    initial_drainage_volume_m3: float = 0.0
    final_drainage_volume_m3: float = 0.0
    closure_error_pct: float = 0.0

    def compute_closure(self) -> float:
        """Compute and store the mass balance closure error percentage."""
        total_in = self.total_rainfall_m3
        total_out = (
            self.total_infiltration_m3
            + self.total_boundary_outflow_m3
        )
        delta_storage = (
            (self.final_surface_volume_m3 - self.initial_surface_volume_m3)
            + (self.final_drainage_volume_m3 - self.initial_drainage_volume_m3)
        )
        residual = total_in - total_out - delta_storage
        denominator = max(total_in, 1e-10)
        self.closure_error_pct = abs(residual) / denominator * 100.0
        return self.closure_error_pct


class SimulationConfig(BaseModel):
    """Configuration for a simulation run."""

    city_id: str
    mode: SimulationMode
    start_time: datetime
    end_time: datetime
    rainfall_source: str = "open_meteo"
    surface_model: str = "landlab_overland"
    drainage_model: str = "pyswmm"
    coupling_model: str = "signed_orifice"
    time_step_s: float = Field(default=1.0, gt=0)
    coupling_stride_s: float = Field(default=60.0, gt=0)
    parameters: dict[str, Any] = Field(default_factory=dict)


class FloodSnapshot(BaseModel):
    """A single time-step output from a flood simulation."""

    run_id: str
    valid_time: datetime
    lead_minutes: int = 0
    max_depth_m: float = 0.0
    mean_depth_m: float = 0.0
    flooded_cells: int = 0
    flooded_area_m2: float = 0.0
    wet_dry_threshold_m: float = 0.05
    depth_grid_uri: Optional[str] = None
    statistics: dict[str, Any] = Field(default_factory=dict)


class SimulationResult(BaseModel):
    """Complete result of a simulation run."""

    run_id: str
    city_id: str
    mode: SimulationMode
    status: SimulationStatus
    config: SimulationConfig
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    mass_balance: Optional[MassBalance] = None
    snapshots: list[FloodSnapshot] = Field(default_factory=list)
    error_message: Optional[str] = None
