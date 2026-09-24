"""Flood depth raster rendering — smooth PNG overlay for Leaflet.

Replaces the ugly GeoJSON square-cell polygons with a proper
raster image overlay that looks like a continuous water surface.

The model grid is rendered to a PNG with:
- Smooth bilinear interpolation
- Semi-transparent water-depth colormap
- No visible cell borders
- Scientific depth scale

The frontend loads this as a Leaflet ImageOverlay with proper bounds.
"""

from __future__ import annotations

import io
import base64
from typing import Optional

import numpy as np
from PIL import Image, ImageFilter
import structlog

logger = structlog.get_logger()

# Water depth colormap: scientific blue gradient
# (depth_threshold, r, g, b, alpha)
DEPTH_COLORS = [
    (0.00, 255, 255, 255, 0),      # Transparent (no water)
    (0.05, 173, 216, 230, 60),     # Light blue, barely visible
    (0.10, 100, 180, 220, 100),    # Soft blue
    (0.20, 65,  150, 210, 140),    # Medium blue
    (0.30, 30,  120, 200, 170),    # Deeper blue
    (0.50, 20,  90,  180, 200),    # Strong blue
    (0.75, 15,  60,  160, 220),    # Dark blue
    (1.00, 180, 50,  50,  230),    # Red-blue for critical
    (1.50, 200, 30,  30,  240),    # Deep red
    (2.00, 160, 20,  20,  250),    # Very deep
]


def depth_to_rgba(depth: float) -> tuple[int, int, int, int]:
    """Map a water depth value to an RGBA color."""
    if depth < 0.05:
        return (0, 0, 0, 0)

    # Find bracketing thresholds
    for i in range(len(DEPTH_COLORS) - 1):
        d0, r0, g0, b0, a0 = DEPTH_COLORS[i]
        d1, r1, g1, b1, a1 = DEPTH_COLORS[i + 1]
        if d0 <= depth <= d1:
            frac = (depth - d0) / (d1 - d0) if (d1 - d0) > 0 else 0
            r = int(r0 + frac * (r1 - r0))
            g = int(g0 + frac * (g1 - g0))
            b = int(b0 + frac * (b1 - b0))
            a = int(a0 + frac * (a1 - a0))
            return (r, g, b, a)

    # Beyond maximum
    return DEPTH_COLORS[-1][1:]


def render_flood_raster(
    depth_grid: np.ndarray,
    upsample_factor: int = 4,
    smooth_radius: float = 1.5,
    min_depth_m: float = 0.05,
) -> Image.Image:
    """Render a flood depth grid as a smooth RGBA image.

    Args:
        depth_grid: 2D array of water depths (metres)
        upsample_factor: Upscale factor for smooth appearance
        smooth_radius: Gaussian blur radius for soft edges
        min_depth_m: Minimum depth to render

    Returns:
        PIL Image (RGBA) ready for PNG encoding
    """
    rows, cols = depth_grid.shape

    # Create base RGBA image at native resolution
    img = Image.new("RGBA", (cols, rows), (0, 0, 0, 0))
    pixels = img.load()

    for r in range(rows):
        for c in range(cols):
            d = float(depth_grid[r, c])
            if d >= min_depth_m:
                pixels[c, r] = depth_to_rgba(d)

    # Upsample for smooth appearance
    new_w = cols * upsample_factor
    new_h = rows * upsample_factor
    img = img.resize((new_w, new_h), Image.BILINEAR)

    # Apply Gaussian blur for soft edges (only to RGB, preserve alpha structure)
    if smooth_radius > 0:
        # Split channels, blur RGB, recombine
        r_ch, g_ch, b_ch, a_ch = img.split()
        r_ch = r_ch.filter(ImageFilter.GaussianBlur(smooth_radius))
        g_ch = g_ch.filter(ImageFilter.GaussianBlur(smooth_radius))
        b_ch = b_ch.filter(ImageFilter.GaussianBlur(smooth_radius))
        a_ch = a_ch.filter(ImageFilter.GaussianBlur(smooth_radius * 0.8))
        img = Image.merge("RGBA", (r_ch, g_ch, b_ch, a_ch))

    return img


def depth_grid_to_png_base64(
    depth_grid: np.ndarray,
    upsample_factor: int = 4,
    smooth_radius: float = 1.5,
    min_depth_m: float = 0.05,
) -> str:
    """Render flood depth grid to a base64-encoded PNG string.

    Used for embedding in JSON API responses.
    """
    img = render_flood_raster(depth_grid, upsample_factor, smooth_radius, min_depth_m)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def depth_grid_to_png_bytes(
    depth_grid: np.ndarray,
    upsample_factor: int = 4,
    smooth_radius: float = 1.5,
    min_depth_m: float = 0.05,
) -> bytes:
    """Render flood depth grid to PNG bytes.

    Used for direct HTTP response.
    """
    img = render_flood_raster(depth_grid, upsample_factor, smooth_radius, min_depth_m)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
