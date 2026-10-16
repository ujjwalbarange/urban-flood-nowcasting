"""Machine Learning Flood Surrogate API Router.

Provides high-speed surrogate model inference, model registry management,
comparative validation benchmarks against 2D physics solver, and training triggers.

Phase 2C-7: ML Surrogate API router.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import structlog
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel

from services.ml.inference import predict_flood_surrogate, SurrogatePredictionResult
from services.ml.registry import get_model_registry, ModelMetadata
from services.ml.evaluate import compute_surrogate_metrics
from services.flood.engine import SimulationConfig, run_simulation
from services.terrain.dem_loader import get_catchment_dem
from services.terrain.conditioning import fill_sinks
import numpy as np

logger = structlog.get_logger()
router = APIRouter(prefix="/ml", tags=["ML Surrogate"])


class MLPredictRequest(BaseModel):
    catchment: str = "hindmata_dadar"
    rainfall_intensity_mmh: float = 50.0
    duration_hours: float = 2.0
    grid_size: int = 40


class MLComparisonResponse(BaseModel):
    catchment: str
    rainfall_intensity_mmh: float
    duration_hours: float
    physics_solver: Dict[str, Any]
    ml_surrogate: Dict[str, Any]
    metrics: Dict[str, Any]
    speedup_factor: str
    recommended_model: str


@router.post("/predict")
async def run_surrogate_prediction(req: MLPredictRequest):
    """Execute sub-second ML surrogate inference for flood extent and depth."""
    try:
        res = predict_flood_surrogate(
            catchment=req.catchment,
            rainfall_intensity_mmh=req.rainfall_intensity_mmh,
            duration_hours=req.duration_hours,
            grid_size=req.grid_size,
        )
        return {
            "status": "success",
            "prediction": res.to_summary_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error("ML surrogate prediction failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"ML surrogate prediction failed: {str(e)}")


@router.get("/models")
async def list_surrogate_models():
    """List all registered ML surrogate models, versions, and deployment statuses."""
    registry = get_model_registry()
    models = registry.list_models()
    return {
        "total_models": len(models),
        "models": [m.to_dict() for m in models],
    }


@router.get("/metrics")
async def get_surrogate_metrics():
    """Get quantitative benchmark metrics (CSI, IoU, RMSE) for active models."""
    registry = get_model_registry()
    active = registry.get_active_model()
    if not active:
        raise HTTPException(status_code=404, detail="No active surrogate model found")

    return {
        "model_id": active.model_id,
        "version": active.version,
        "architecture": active.architecture,
        "benchmarks": active.benchmark_metrics,
        "validation_dataset": "Sentinel-1 SAR + 2D Diffusive Wave Synthetic Archive",
    }


@router.get("/compare", response_model=MLComparisonResponse)
async def compare_physics_vs_ml(
    catchment: str = Query("hindmata_dadar", description="Catchment to simulate"),
    rainfall_intensity_mmh: float = Query(45.0, ge=5.0, le=200.0),
    duration_hours: float = Query(2.0, ge=0.5, le=6.0),
    grid_size: int = Query(32, ge=20, le=60),
):
    """Run side-by-side comparison between 2D physics solver and ConvGRU surrogate."""
    # 1. Run ML Surrogate
    ml_res = predict_flood_surrogate(
        catchment=catchment,
        rainfall_intensity_mmh=rainfall_intensity_mmh,
        duration_hours=duration_hours,
        grid_size=grid_size,
    )

    # 2. Run Physics Simulation
    dem_raw, georef = get_catchment_dem(catchment, max_dim=grid_size)
    dem = fill_sinks(dem_raw.astype(np.float64))
    schedule = [(0.0, rainfall_intensity_mmh), (duration_hours, rainfall_intensity_mmh)]
    cfg = SimulationConfig(
        city_id="mumbai",
        duration_hours=duration_hours,
        cell_size_m=georef["cell_size_m"],
        manning_n=0.035,
    )
    import time
    t0 = time.time()
    physics_res = run_simulation(
        dem=dem,
        rainfall_schedule=schedule,
        imperviousness=np.full(dem.shape, 0.75),
        config=cfg,
    )
    physics_runtime_ms = (time.time() - t0) * 1000.0

    # 3. Compute Metrics
    metrics = compute_surrogate_metrics(
        pred_depth=ml_res.depth_grid,
        target_depth=physics_res.max_depth_grid,
    )

    speedup = f"{round(physics_runtime_ms / max(1.0, ml_res.inference_latency_ms), 1)}x"

    return MLComparisonResponse(
        catchment=catchment,
        rainfall_intensity_mmh=rainfall_intensity_mmh,
        duration_hours=duration_hours,
        physics_solver={
            "solver": "2D Diffusive Wave",
            "runtime_ms": round(physics_runtime_ms, 1),
            "max_depth_m": round(float(physics_res.max_depth_m), 4),
            "mass_balance_error_pct": round(physics_res.mass_balance.compute_closure(), 3),
        },
        ml_surrogate={
            "model_version": ml_res.model_version,
            "runtime_ms": round(ml_res.inference_latency_ms, 1),
            "max_depth_m": round(ml_res.max_depth_m, 4),
        },
        metrics=metrics.to_dict(),
        speedup_factor=speedup,
        recommended_model="physics" if metrics.csi < 0.5 else "ml_surrogate_for_nowcasting",
    )


@router.post("/train")
async def trigger_training(
    background_tasks: BackgroundTasks,
    catchment: str = Query("hindmata_dadar"),
    epochs: int = Query(3, ge=1, le=20),
):
    """Trigger background retraining of the surrogate model on physics data."""
    def run_train():
        from services.ml.dataset import create_dataloaders
        from services.ml.train import train_surrogate_model
        train_loader, val_loader, _ = create_dataloaders(num_samples_if_none=8, grid_size=32)
        train_surrogate_model(
            train_loader=train_loader,
            val_loader=val_loader,
            epochs=epochs,
            save_path=f"data/models/checkpoints/convgru_{catchment}_latest.pt",
        )

    background_tasks.add_task(run_train)
    return {
        "status": "queued",
        "catchment": catchment,
        "epochs": epochs,
        "message": "Surrogate model training launched in background.",
    }
