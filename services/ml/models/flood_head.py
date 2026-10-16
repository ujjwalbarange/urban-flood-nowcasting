"""Dual-output flood prediction head — adapted from U-RNN (MIT License).

Original: Cao et al., "U-RNN", Journal of Hydrology, 2025.
Source: https://github.com/holmescao/U-RNN (MIT License)

The dual-head produces:
1. Classification: wet/dry probability per cell (sigmoid output)
2. Regression: flood depth per cell (LeakyReLU output, ≥ 0)

Key innovation: correction_depth() zeros out depth at cells classified as dry,
enforcing consistency between the two outputs.
"""

import torch
import torch.nn as nn


class FloodPredictionHead(nn.Module):
    """Dual-output prediction head for flood depth and extent.

    Adapted from U-RNN's YOLOXHead (MIT License).

    Args:
        in_channels: Input feature channels from decoder
        hidden_channels: Internal channel width (default 32)
        cls_threshold: Wet/dry threshold for depth correction (default 0.5)
    """

    def __init__(
        self,
        in_channels: int = 32,
        hidden_channels: int = 16,
        cls_threshold: float = 0.5,
    ):
        super().__init__()
        self.cls_threshold = cls_threshold

        # Shared stem
        self.stem = nn.Sequential(
            nn.Conv2d(in_channels, hidden_channels, 1, 1, 0),
            nn.GroupNorm(max(1, hidden_channels // 8), hidden_channels),
            nn.SiLU(),
        )

        # Classification branch: wet/dry probability
        self.cls_branch = nn.Sequential(
            nn.Conv2d(hidden_channels, hidden_channels, 3, 1, 1),
            nn.GroupNorm(max(1, hidden_channels // 8), hidden_channels),
            nn.SiLU(),
            nn.Conv2d(hidden_channels, 1, 1, 1, 0),
            nn.Sigmoid(),
        )

        # Regression branch: flood depth
        self.reg_branch = nn.Sequential(
            nn.Conv2d(hidden_channels, hidden_channels, 3, 1, 1),
            nn.GroupNorm(max(1, hidden_channels // 8), hidden_channels),
            nn.SiLU(),
            nn.Conv2d(hidden_channels, 1, 1, 1, 0),
            nn.LeakyReLU(0.1),  # Depth ≥ 0 (small negative leak for gradient flow)
        )

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        """Predict flood depth and extent.

        Args:
            x: Feature maps (B, C, H, W)

        Returns:
            Dict with:
                'depth': (B, 1, H, W) — corrected flood depth
                'extent': (B, 1, H, W) — wet/dry probability [0, 1]
                'depth_raw': (B, 1, H, W) — uncorrected depth (for analysis)
        """
        features = self.stem(x)
        cls_output = self.cls_branch(features)   # (B, 1, H, W) wet probability
        reg_output = self.reg_branch(features)   # (B, 1, H, W) raw depth

        # Correction: zero out depth at cells classified as dry
        depth_corrected = self.correction_depth(reg_output, cls_output)

        return {
            "depth": depth_corrected,
            "extent": cls_output,
            "depth_raw": reg_output,
        }

    def correction_depth(
        self,
        depth: torch.Tensor,
        extent: torch.Tensor,
    ) -> torch.Tensor:
        """Apply classification mask to depth predictions.

        Cells with wet probability < threshold have depth set to 0.
        This prevents false positive depth values in dry areas.

        From U-RNN flood_head.py (MIT License).
        """
        wet_mask = (extent >= self.cls_threshold).float()
        return torch.clamp(depth, min=0.0) * wet_mask
