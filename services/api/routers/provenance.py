"""FastAPI router for Data Provenance, Feed Health & Model Run Audit (Phase 5).

Exposes:
- GET /api/v1/provenance/feeds: Monitored external data feeds with status, freshness, and classification.
- GET /api/v1/provenance/runs: Simulation lifecycle audit log with input tracing and validation checks.
- GET /api/v1/provenance/runs/{run_id}: Detailed provenance for a specific model run.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from services.provenance.engine import get_provenance_registry

router = APIRouter(prefix="/provenance", tags=["Data Provenance & Health"])


@router.get("/feeds")
async def list_monitored_data_feeds():
    """List all 8 core MUFNS data feeds with evaluated freshness, age, and classification."""
    registry = get_provenance_registry()
    feeds = registry.list_feeds()
    return {
        "total_feeds": len(feeds),
        "feeds": feeds,
        "classification_guide": {
            "observed": "Direct physical sensor/gauge/satellite measurement",
            "forecast": "Numerical Weather Prediction (NWP) model projection",
            "derived": "Computed from observations via validated physical algorithms",
            "inferred": "Spatially or statistically interpolated from sparse data",
            "synthetic": "Procedurally generated or engineering assumption (not ground truth)",
        },
    }


@router.get("/runs")
async def list_simulation_runs(limit: int = Query(20, ge=1, le=100)):
    """List recent simulation runs with full provenance and output validation status."""
    registry = get_provenance_registry()
    runs = registry.list_simulation_runs(limit=limit)
    return {
        "total_runs": len(runs),
        "runs": runs,
    }


@router.get("/runs/{run_id}")
async def get_simulation_run_provenance(run_id: str):
    """Retrieve full audit record for a specific simulation run."""
    registry = get_provenance_registry()
    run = registry.get_simulation_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Simulation run '{run_id}' not found in provenance registry.")
    return run.to_dict()
