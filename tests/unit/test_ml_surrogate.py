"""Unit tests for ML Surrogate pipeline (Phase 2C)."""

import pytest
import torch
from httpx import AsyncClient, ASGITransport

from services.api.main import app
from services.ml.data_generator import FloodDataGenerator
from services.ml.dataset import create_dataloaders
from services.ml.train import FloodSurrogateModel
from services.ml.evaluate import compute_surrogate_metrics
from services.ml.registry import get_model_registry
from services.ml.inference import predict_flood_surrogate


def test_data_generator_and_tensors():
    """Verify data generator produces valid tensor shapes for surrogate training."""
    gen = FloodDataGenerator()
    sample = gen.generate_single_sample(
        catchment="hindmata_dadar",
        rainfall_intensity_mmh=40.0,
        duration_hours=1.0,
        grid_size=24,
    )

    assert sample is not None
    assert sample.dem_tensor.ndim == 3  # (1, H, W)
    assert sample.rainfall_tensor.ndim == 4  # (T, 1, H, W)
    assert sample.target_depth_tensor.ndim == 4  # (T, 1, H, W)
    assert sample.max_depth_m >= 0.0


def test_dataset_and_dataloader_splits():
    """Verify train/val/test splits and batch formatting."""
    train_loader, val_loader, test_loader = create_dataloaders(
        num_samples_if_none=4,
        batch_size=2,
        grid_size=24,
    )

    assert len(train_loader) > 0
    assert len(val_loader) > 0
    assert len(test_loader) > 0

    batch = next(iter(train_loader))
    assert "x" in batch
    assert "y_depth" in batch
    assert "y_mask" in batch
    # x has shape (B, T, 2, H, W)
    assert batch["x"].ndim == 5
    assert batch["x"].shape[2] == 2


def test_surrogate_model_forward():
    """Verify forward pass of SkipConvGRU + FloodPredictionHead."""
    model = FloodSurrogateModel(in_channels=2, hidden_channels=8, num_layers=2)
    # Dummy batch: (B=2, T=3, C=2, H=16, W=16)
    x = torch.randn(2, 3, 2, 16, 16)
    out = model(x)

    assert "pred_cls" in out
    assert "pred_depth" in out
    assert "corrected_depth" in out

    assert out["pred_cls"].shape == (2, 3, 1, 16, 16)
    assert out["pred_depth"].shape == (2, 3, 1, 16, 16)
    assert out["corrected_depth"].shape == (2, 3, 1, 16, 16)

    # Check that corrected depth is non-negative
    assert torch.all(out["corrected_depth"] >= 0.0)


def test_surrogate_evaluation_metrics():
    """Verify evaluation metric calculations."""
    import numpy as np
    y_true = np.zeros((20, 20), dtype=np.float32)
    y_true[5:15, 5:15] = 0.5  # 100 cells flooded

    y_pred = np.zeros((20, 20), dtype=np.float32)
    y_pred[7:17, 7:17] = 0.45  # 100 cells, partially overlapping

    metrics = compute_surrogate_metrics(y_pred, y_true, flood_threshold_m=0.10)
    assert 0.0 < metrics.csi <= 1.0
    assert 0.0 < metrics.iou <= 1.0
    assert metrics.mae_depth_m >= 0.0
    assert metrics.rmse_depth_m >= 0.0


def test_model_registry():
    """Verify model registry returns active models and metadata."""
    registry = get_model_registry()
    models = registry.list_models()
    assert len(models) >= 1

    active = registry.get_active_model()
    assert active is not None
    assert active.status == "ACTIVE"
    assert "csi" in active.benchmark_metrics


def test_surrogate_inference_speed():
    """Verify surrogate inference executes in under 500ms on CPU."""
    res = predict_flood_surrogate(
        catchment="hindmata_dadar",
        rainfall_intensity_mmh=50.0,
        duration_hours=1.0,
        grid_size=24,
    )

    assert res is not None
    assert res.inference_latency_ms < 500.0  # Fast sub-second inference
    assert res.depth_grid.ndim == 2
    assert res.max_depth_m >= 0.0


@pytest.mark.asyncio
async def test_ml_api_endpoints():
    """Verify /api/v1/ml endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Models
        r = await client.get("/api/v1/ml/models")
        assert r.status_code == 200
        data = r.json()
        assert data["total_models"] >= 1

        # Metrics
        r = await client.get("/api/v1/ml/metrics")
        assert r.status_code == 200
        data = r.json()
        assert "benchmarks" in data

        # Predict
        r = await client.post("/api/v1/ml/predict", json={
            "catchment": "hindmata_dadar",
            "rainfall_intensity_mmh": 35.0,
            "duration_hours": 1.0,
            "grid_size": 24,
        })
        assert r.status_code == 200
        pred = r.json()["prediction"]
        assert "max_depth_m" in pred
        assert "inference_latency_ms" in pred
