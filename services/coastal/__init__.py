"""Coastal and tide integration module."""
from services.coastal.tide_service import (
    TideService,
    TideScenario,
    TideBoundarySchedule,
    identify_coastal_boundary_mask,
    MUMBAI_DATUM_OFFSET_M,
    MUMBAI_MHWS_M_CD,
    MUMBAI_MHWN_M_CD,
    MUMBAI_EXTREME_M_CD,
)

__all__ = [
    "TideService",
    "TideScenario",
    "TideBoundarySchedule",
    "identify_coastal_boundary_mask",
    "MUMBAI_DATUM_OFFSET_M",
    "MUMBAI_MHWS_M_CD",
    "MUMBAI_MHWN_M_CD",
    "MUMBAI_EXTREME_M_CD",
]
