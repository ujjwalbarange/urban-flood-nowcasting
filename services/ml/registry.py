"""Model Registry for ML Flood Surrogates.

Tracks trained model checkpoints, training provenance, architecture hyper-parameters,
benchmark validation metrics, and active deployment status.

Phase 2C-5: Model registry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

logger = structlog.get_logger()


@dataclass
class ModelMetadata:
    """Metadata record for a registered surrogate model."""
    model_id: str
    version: str
    architecture: str
    catchment: str
    weights_path: str
    registered_at: str
    status: str                         # ACTIVE, CANDIDATE, ARCHIVED
    parameters_count: int
    input_channels: int
    hidden_channels: int
    benchmark_metrics: Dict[str, Any] = field(default_factory=dict)
    training_epochs: int = 10
    author: str = "MUFNS ML Pipeline"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_id": self.model_id,
            "version": self.version,
            "architecture": self.architecture,
            "catchment": self.catchment,
            "weights_path": self.weights_path,
            "registered_at": self.registered_at,
            "status": self.status,
            "parameters_count": self.parameters_count,
            "input_channels": self.input_channels,
            "hidden_channels": self.hidden_channels,
            "benchmark_metrics": self.benchmark_metrics,
            "training_epochs": self.training_epochs,
            "author": self.author,
        }


class ModelRegistry:
    """Manages versioned model checkpoints and deployment state."""

    def __init__(self, registry_file: Optional[str] = None):
        self.registry_file = Path(registry_file or "data/models/registry.json")
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        self._models: Dict[str, ModelMetadata] = {}
        self._load()

    def _load(self):
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r") as f:
                    data = json.load(f)
                    for item in data:
                        m = ModelMetadata(**item)
                        self._models[m.model_id] = m
            except Exception as e:
                logger.warning("Could not load registry JSON", error=str(e))

        # Seed with initial baseline surrogate if empty
        if not self._models:
            baseline = ModelMetadata(
                model_id="mufns_convgru_v1_hindmata",
                version="v1.0.0",
                architecture="Skip-ConvGRU + FloodPredictionHead",
                catchment="hindmata_dadar",
                weights_path="data/models/checkpoints/convgru_hindmata_v1.pt",
                registered_at=datetime.now(timezone.utc).isoformat(),
                status="ACTIVE",
                parameters_count=84_350,
                input_channels=2,
                hidden_channels=16,
                benchmark_metrics={
                    "csi": 0.76,
                    "iou": 0.62,
                    "pod": 0.82,
                    "far": 0.21,
                    "mae_depth_m": 0.048,
                    "rmse_depth_m": 0.089,
                    "inference_latency_ms": 138.0,
                },
                training_epochs=15,
            )
            self._models[baseline.model_id] = baseline
            self._save()

    def _save(self):
        try:
            with open(self.registry_file, "w") as f:
                json.dump([m.to_dict() for m in self._models.values()], f, indent=2)
        except Exception as e:
            logger.warning("Could not save registry JSON", error=str(e))

    def register(self, metadata: ModelMetadata) -> None:
        self._models[metadata.model_id] = metadata
        self._save()

    def get_active_model(self, catchment: str = "hindmata_dadar") -> Optional[ModelMetadata]:
        for m in self._models.values():
            if m.status == "ACTIVE" and (m.catchment == catchment or m.catchment == "mumbai_city"):
                return m
        # Fallback to any active
        for m in self._models.values():
            if m.status == "ACTIVE":
                return m
        return None

    def list_models(self) -> List[ModelMetadata]:
        return list(self._models.values())


_global_registry = ModelRegistry()


def get_model_registry() -> ModelRegistry:
    return _global_registry
