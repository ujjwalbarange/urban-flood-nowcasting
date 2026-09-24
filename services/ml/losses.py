"""Curriculum loss functions — adapted from U-RNN (MIT License).

Original: Cao et al., "U-RNN", Journal of Hydrology, 2025.
Source: https://github.com/holmescao/U-RNN (MIT License)

Loss components:
1. FocalBCE: Focal Binary Cross-Entropy for wet/dry classification
   - Addresses 80:20 dry:wet class imbalance
   - Down-weights easy (correctly classified) samples

2. WeightedMSE: Weighted MSE for depth regression
   - Up-weights flooded cells by 20x to counter sparsity
   - Prevents model from predicting all-zero depth

3. CurriculumLoss: Combined loss with epoch-dependent weighting
   - Early epochs: prioritize extent classification (easier task)
   - Later epochs: shift focus to depth regression (harder task)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalBCELoss(nn.Module):
    """Focal Binary Cross-Entropy for wet/dry flood extent.

    Adapted from U-RNN losses.py (MIT License).
    Standard BCE is biased toward majority dry cells (~80%).
    Focal loss modulates each sample's loss by (1-p̂)^γ,
    focusing training on hard-to-classify boundary cells.

    Args:
        gamma: Focusing parameter (default 2.0)
        alpha: Balance factor for wet (positive) class (default 0.25)
    """

    def __init__(self, gamma: float = 2.0, alpha: float = 0.25):
        super().__init__()
        self.gamma = gamma
        self.alpha = alpha

    def forward(self, pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """Compute focal BCE loss.

        Args:
            pred: Predicted wet probability [0, 1], shape (B, 1, H, W)
            target: Binary wet/dry labels {0, 1}, shape (B, 1, H, W)
        """
        eps = 1e-9
        pt = pred.clamp(eps, 1 - eps)

        loss = (
            -self.alpha * (1 - pt) ** self.gamma * target * torch.log(pt + eps)
            - (1 - self.alpha) * pt ** self.gamma * (1 - target) * torch.log(1 - pt + eps)
        )
        return loss.mean()


class WeightedMSELoss(nn.Module):
    """Weighted MSE for flood depth regression.

    Adapted from U-RNN losses.py (MIT License).
    Up-weights flooded cells by factor of 20 to counter the ~80% dry
    cell dominance. Without this, MSE drives the model to predict
    zero everywhere (easy but useless).

    Args:
        wet_weight: Multiplication factor for wet-cell MSE (default 20)
    """

    def __init__(self, wet_weight: float = 20.0):
        super().__init__()
        self.wet_weight = wet_weight

    def forward(
        self, pred: torch.Tensor, target: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Compute weighted MSE.

        Args:
            pred: Predicted depth, shape (B, 1, H, W)
            target: Ground truth depth, shape (B, 1, H, W)

        Returns:
            (total_loss, wet_cell_mse, dry_cell_mse)
        """
        wet_mask = target > 0
        dry_mask = ~wet_mask

        wet_pred = torch.masked_select(pred, wet_mask)
        wet_target = torch.masked_select(target, wet_mask)
        dry_pred = torch.masked_select(pred, dry_mask)
        dry_target = torch.masked_select(target, dry_mask)

        wet_mse = F.mse_loss(wet_pred, wet_target) if wet_pred.numel() > 0 else torch.tensor(0.0)
        dry_mse = F.mse_loss(dry_pred, dry_target) if dry_pred.numel() > 0 else torch.tensor(0.0)

        total = self.wet_weight * wet_mse + dry_mse
        return total, wet_mse, dry_mse


class CurriculumLoss(nn.Module):
    """Combined curriculum loss for flood prediction.

    Adapted from U-RNN FocalBCE_and_WMSE (MIT License).

    Curriculum strategy:
    - Phase 1 (epoch < transition): L = L_depth + 10 * L_extent
      Learn extent first (easier binary classification task)
    - Phase 2 (epoch >= transition): L = L_depth + 0.1 * L_extent
      Shift focus to depth regression (harder, but extent is now reliable)

    Args:
        transition_epoch: Epoch to switch curriculum phase (default 500)
        gamma: Focal loss gamma (default 2.0)
        alpha: Focal loss alpha (default 0.25)
        wet_weight: WeightedMSE wet cell factor (default 20.0)
    """

    def __init__(
        self,
        transition_epoch: int = 500,
        gamma: float = 2.0,
        alpha: float = 0.25,
        wet_weight: float = 20.0,
    ):
        super().__init__()
        self.transition_epoch = transition_epoch
        self.focal_bce = FocalBCELoss(gamma=gamma, alpha=alpha)
        self.weighted_mse = WeightedMSELoss(wet_weight=wet_weight)

    def forward(
        self,
        pred_depth: torch.Tensor,
        pred_extent: torch.Tensor,
        target_depth: torch.Tensor,
        epoch: int,
    ) -> dict[str, torch.Tensor]:
        """Compute curriculum-weighted combined loss.

        Args:
            pred_depth: Predicted depth (B, 1, H, W)
            pred_extent: Predicted wet probability (B, 1, H, W)
            target_depth: Ground truth depth (B, 1, H, W)
            epoch: Current training epoch

        Returns:
            Dict with loss, loss_depth, loss_extent, loss_wet, loss_dry
        """
        # Convert depth targets to binary wet/dry labels
        target_extent = (target_depth > 0).float()

        # Compute individual losses
        loss_extent = self.focal_bce(pred_extent, target_extent)
        loss_depth, loss_wet, loss_dry = self.weighted_mse(pred_depth, target_depth)

        # Curriculum weighting
        if epoch < self.transition_epoch:
            cls_weight = 10.0  # Prioritize extent learning
        else:
            cls_weight = 0.1   # Shift to depth refinement

        total_loss = loss_depth + cls_weight * loss_extent

        return {
            "loss": total_loss,
            "loss_depth": loss_depth,
            "loss_extent": loss_extent,
            "loss_wet": loss_wet,
            "loss_dry": loss_dry,
            "curriculum_phase": "extent" if epoch < self.transition_epoch else "depth",
        }
