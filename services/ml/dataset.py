"""PyTorch Dataset and DataLoader for Flood Surrogate Models.

Provides Dataset classes and DataLoader builders with 70/15/15 train/val/test splits
for spatial and spatio-temporal flood depth regression and wet/dry classification.

Phase 2C-2: Dataset & DataLoader pipeline.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import torch
from torch.utils.data import Dataset, DataLoader

from services.ml.data_generator import FloodDataGenerator, SimulationSample


class FloodSurrogateDataset(Dataset):
    """PyTorch Dataset for urban flood surrogate training."""

    def __init__(self, samples: List[SimulationSample]):
        self.samples = samples

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        s = self.samples[idx]

        # Combine DEM and rainfall into input features
        # If rainfall has T steps, expand DEM across time
        T_rain = s.rainfall_tensor.shape[0]
        H, W = s.dem_tensor.shape[1], s.dem_tensor.shape[2]

        dem_repeated = s.dem_tensor.unsqueeze(0).repeat(T_rain, 1, 1, 1)  # (T_rain, 1, H, W)
        x_features = torch.cat([s.rainfall_tensor, dem_repeated], dim=1)   # (T_rain, 2, H, W)

        # Truncate or match sequence length with targets
        T_out = s.target_depth_tensor.shape[0]
        min_t = min(T_rain, T_out)

        return {
            "x": x_features[:min_t],                       # (T, 2, H, W)
            "y_depth": s.target_depth_tensor[:min_t],     # (T, 1, H, W)
            "y_mask": s.target_mask_tensor[:min_t],       # (T, 1, H, W)
            "sample_id": s.sample_id,
        }


def create_dataloaders(
    samples: Optional[List[SimulationSample]] = None,
    batch_size: int = 2,
    num_samples_if_none: int = 12,
    grid_size: int = 32,
) -> Tuple[DataLoader, DataLoader, DataLoader]:
    """Create train, validation, and test DataLoaders with a 70/15/15 split."""
    if samples is None:
        generator = FloodDataGenerator()
        samples = generator.generate_dataset_batch(
            catchment="hindmata_dadar",
            num_samples=num_samples_if_none,
            grid_size=grid_size,
        )

    n_total = len(samples)
    n_train = max(1, int(0.70 * n_total))
    n_val = max(1, int(0.15 * n_total))
    n_test = max(1, n_total - n_train - n_val)

    train_samples = samples[:n_train]
    val_samples = samples[n_train:n_train + n_val]
    test_samples = samples[n_train + n_val:]

    train_loader = DataLoader(
        FloodSurrogateDataset(train_samples),
        batch_size=batch_size,
        shuffle=True,
    )
    val_loader = DataLoader(
        FloodSurrogateDataset(val_samples),
        batch_size=batch_size,
        shuffle=False,
    )
    test_loader = DataLoader(
        FloodSurrogateDataset(test_samples),
        batch_size=batch_size,
        shuffle=False,
    )

    return train_loader, val_loader, test_loader
