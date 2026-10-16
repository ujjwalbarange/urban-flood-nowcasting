"""Training Routine for Urban Flood ConvGRU Surrogate Model.

Trains dual-output spatio-temporal neural network surrogate using:
- SkipConvGRUEncoder and SkipConvGRUDecoder (Cao et al., U-RNN)
- FloodPredictionHead (wet/dry probability + non-negative water depth)
- CurriculumLoss (FocalBCE + WeightedMSE)

Phase 2C-3: Surrogate model training pipeline.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog
import torch
import torch.nn as nn
from torch.utils.data import DataLoader

from services.ml.models.conv_gru import (
    ConvGRUEncoder,
    ConvGRUDecoder,
    SkipConvGRUEncoder,
    SkipConvGRUDecoder,
)
from services.ml.models.flood_head import FloodPredictionHead
from services.ml.losses import CurriculumLoss
from services.ml.dataset import create_dataloaders

logger = structlog.get_logger()


class FloodSurrogateModel(nn.Module):
    """End-to-end surrogate model: Encoder -> Decoder -> Dual-head."""

    def __init__(
        self,
        in_channels: int = 2,       # Rainfall + DEM
        features: list[int] | None = None,
        hidden_channels: int = 16,
        num_layers: int = 2,
    ):
        super().__init__()
        if features is None:
            features = [hidden_channels, hidden_channels * 2]
        self.features = features
        self.encoder = ConvGRUEncoder(
            input_channels=in_channels,
            features=features,
            kernel_size=3,
        )
        self.decoder = ConvGRUDecoder(
            features=features,
            kernel_size=3,
        )
        self.head = FloodPredictionHead(
            in_channels=features[0],
            hidden_channels=16,
            cls_threshold=0.5,
        )

    def forward(
        self,
        x: torch.Tensor,  # (B, T, C, H, W)
    ) -> Dict[str, torch.Tensor]:
        """Forward pass through encoder, decoder, and dual head."""
        B, T, C, H, W = x.shape
        enc_states = None
        dec_states = None

        cls_list = []
        reg_list = []
        corr_list = []

        for t in range(T):
            x_t = x[:, t : t + 1, :, :, :].permute(1, 0, 2, 3, 4)  # (1, B, C, H, W)
            enc_states = self.encoder(x_t, states=enc_states)
            dec_states = self.decoder(encoder_states=enc_states, decoder_states=dec_states)
            head_out = self.head(dec_states[0])
            cls_list.append(head_out["extent"].unsqueeze(1))
            reg_list.append(head_out["depth_raw"].unsqueeze(1))
            corr_list.append(head_out["depth"].unsqueeze(1))

        return {
            "pred_cls": torch.cat(cls_list, dim=1),
            "pred_depth": torch.cat(reg_list, dim=1),
            "corrected_depth": torch.cat(corr_list, dim=1),
        }


def train_surrogate_model(
    train_loader: DataLoader,
    val_loader: DataLoader,
    epochs: int = 3,
    lr: float = 1e-3,
    save_path: Optional[str] = None,
    device: str = "cpu",
) -> Dict[str, Any]:
    """Execute training loop for surrogate model."""
    device_obj = torch.device(device)
    model = FloodSurrogateModel(in_channels=2, hidden_channels=16, num_layers=2).to(device_obj)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    criterion = CurriculumLoss(total_epochs=epochs, initial_cls_weight=0.7)

    history = {"train_loss": [], "val_loss": []}

    for epoch in range(epochs):
        model.train()
        total_train_loss = 0.0
        train_batches = 0

        for batch in train_loader:
            x = batch["x"].to(device_obj)                # (B, T, 2, H, W)
            y_depth = batch["y_depth"].to(device_obj)    # (B, T, 1, H, W)
            y_mask = batch["y_mask"].to(device_obj)      # (B, T, 1, H, W)

            optimizer.zero_grad()
            out = model(x)

            # Flatten time and batch for loss
            B, T = x.shape[:2]
            pred_cls_flat = out["pred_cls"].view(B * T, 1, x.shape[3], x.shape[4])
            pred_reg_flat = out["pred_depth"].view(B * T, 1, x.shape[3], x.shape[4])
            y_mask_flat = y_mask.view(B * T, 1, x.shape[3], x.shape[4])
            y_depth_flat = y_depth.view(B * T, 1, x.shape[3], x.shape[4])

            loss, _, _ = criterion(
                pred_cls=pred_cls_flat,
                pred_reg=pred_reg_flat,
                target_cls=y_mask_flat,
                target_reg=y_depth_flat,
                epoch=epoch,
            )

            loss.backward()
            optimizer.step()

            total_train_loss += loss.item()
            train_batches += 1

        avg_train_loss = total_train_loss / max(1, train_batches)
        history["train_loss"].append(round(avg_train_loss, 4))

        # Validation
        model.eval()
        total_val_loss = 0.0
        val_batches = 0
        with torch.no_grad():
            for batch in val_loader:
                x = batch["x"].to(device_obj)
                y_depth = batch["y_depth"].to(device_obj)
                y_mask = batch["y_mask"].to(device_obj)
                out = model(x)

                B, T = x.shape[:2]
                pred_cls_flat = out["pred_cls"].view(B * T, 1, x.shape[3], x.shape[4])
                pred_reg_flat = out["pred_depth"].view(B * T, 1, x.shape[3], x.shape[4])
                y_mask_flat = y_mask.view(B * T, 1, x.shape[3], x.shape[4])
                y_depth_flat = y_depth.view(B * T, 1, x.shape[3], x.shape[4])

                val_loss, _, _ = criterion(
                    pred_cls=pred_cls_flat,
                    pred_reg=pred_reg_flat,
                    target_cls=y_mask_flat,
                    target_reg=y_depth_flat,
                    epoch=epoch,
                )
                total_val_loss += val_loss.item()
                val_batches += 1

        avg_val_loss = total_val_loss / max(1, val_batches)
        history["val_loss"].append(round(avg_val_loss, 4))

        logger.info(
            "Surrogate epoch complete",
            epoch=epoch + 1,
            train_loss=round(avg_train_loss, 4),
            val_loss=round(avg_val_loss, 4),
        )

    # Save model checkpoint
    if save_path:
        p = Path(save_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            "model_state_dict": model.state_dict(),
            "epochs": epochs,
            "val_loss": history["val_loss"][-1],
        }, str(p))
        logger.info("Saved surrogate model weights", path=str(p))

    return {
        "status": "completed",
        "epochs": epochs,
        "final_train_loss": history["train_loss"][-1] if history["train_loss"] else 0.0,
        "final_val_loss": history["val_loss"][-1] if history["val_loss"] else 0.0,
        "history": history,
        "model": model,
    }
