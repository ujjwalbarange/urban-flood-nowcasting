"""Drainage network graph construction and SWMM input generation.

Builds a graph representation of the drainage network from PostGIS data,
and generates EPA SWMM 5.2 .inp files for hydraulic simulation.

The drainage network is represented as:
- Nodes: manholes, inlets, outfalls, junctions
- Links: pipes, channels, culverts

When real MCGM data is unavailable (current state), this module
can generate a SYNTHETIC drainage network from DEM flow accumulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np
import structlog

from packages.contracts.drainage import (
    DrainageLink,
    DrainageLinkType,
    DrainageNode,
    DrainageNodeType,
)
from packages.contracts.provenance import DataQuality

logger = structlog.get_logger()


@dataclass
class DrainageNetwork:
    """In-memory representation of a city's drainage network.

    This is the graph that feeds into SWMM and the coupling engine.
    """

    city_id: str
    nodes: dict[str, DrainageNode] = field(default_factory=dict)
    links: dict[str, DrainageLink] = field(default_factory=dict)

    @property
    def node_count(self) -> int:
        return len(self.nodes)

    @property
    def link_count(self) -> int:
        return len(self.links)

    def add_node(self, node: DrainageNode) -> None:
        self.nodes[node.node_id] = node

    def add_link(self, link: DrainageLink) -> None:
        self.links[link.link_id] = link

    def get_downstream_nodes(self, node_id: str) -> list[str]:
        """Find all nodes downstream of the given node."""
        return [
            link.to_node
            for link in self.links.values()
            if link.from_node == node_id
        ]

    def get_upstream_nodes(self, node_id: str) -> list[str]:
        """Find all nodes upstream of the given node."""
        return [
            link.from_node
            for link in self.links.values()
            if link.to_node == node_id
        ]

    def get_outfalls(self) -> list[DrainageNode]:
        """Get all outfall nodes."""
        return [n for n in self.nodes.values() if n.node_type == DrainageNodeType.OUTFALL]

    def validate(self) -> list[str]:
        """Check network integrity. Returns list of issues."""
        issues = []
        for link in self.links.values():
            if link.from_node not in self.nodes:
                issues.append(f"Link {link.link_id}: from_node '{link.from_node}' not found")
            if link.to_node not in self.nodes:
                issues.append(f"Link {link.link_id}: to_node '{link.to_node}' not found")
        if not self.get_outfalls():
            issues.append("No outfall nodes defined — water cannot leave the network")
        return issues


def generate_synthetic_network(
    dem: np.ndarray,
    flow_accumulation: np.ndarray,
    cell_size_m: float,
    origin_x: float,
    origin_y: float,
    city_id: str,
    accumulation_threshold: int = 500,
    spacing_cells: int = 20,
) -> DrainageNetwork:
    """Generate a synthetic drainage network from DEM flow accumulation.

    Places nodes at high-accumulation cells (potential drain locations)
    and connects them following the flow direction.

    This is the FALLBACK when real drainage data is unavailable.
    All generated data is marked with data_quality='assumed'.

    Args:
        dem: 2D elevation array
        flow_accumulation: D8 flow accumulation array
        cell_size_m: Grid cell size in metres
        origin_x, origin_y: Grid origin in projected CRS
        city_id: City identifier
        accumulation_threshold: Min accumulation to place a node
        spacing_cells: Minimum spacing between nodes

    Returns:
        Synthetic DrainageNetwork
    """
    rows, cols = dem.shape
    network = DrainageNetwork(city_id=city_id)

    # Find candidate node locations (high flow accumulation, spaced out)
    candidates = []
    for r in range(spacing_cells, rows - spacing_cells, spacing_cells):
        for c in range(spacing_cells, cols - spacing_cells, spacing_cells):
            if flow_accumulation[r, c] >= accumulation_threshold:
                candidates.append((r, c, flow_accumulation[r, c]))

    # Sort by accumulation (highest first = most important)
    candidates.sort(key=lambda x: -x[2])

    # Create nodes
    node_id_counter = 0
    cell_to_node = {}

    for r, c, acc in candidates:
        # Determine node type
        if r <= 2 or r >= rows - 3 or c <= 2 or c >= cols - 3:
            node_type = DrainageNodeType.OUTFALL
        elif acc > accumulation_threshold * 10:
            node_type = DrainageNodeType.JUNCTION
        else:
            node_type = DrainageNodeType.MANHOLE

        # Convert cell to projected coordinates → WGS84
        x = origin_x + (c + 0.5) * cell_size_m
        y = origin_y - (r + 0.5) * cell_size_m
        elevation = float(dem[r, c])

        node_id = f"syn_n_{node_id_counter:04d}"
        node = DrainageNode(
            node_id=node_id,
            city_id=city_id,
            node_type=node_type,
            latitude=0.0,  # Will be converted from projected coords
            longitude=0.0,
            ground_elevation_m=elevation,
            invert_elevation_m=elevation - 2.0,  # Assume 2m cover depth
            data_quality=DataQuality.ASSUMED,
            attributes={
                "synthetic": True,
                "flow_accumulation": int(acc),
                "grid_row": r,
                "grid_col": c,
                "projected_x": x,
                "projected_y": y,
            },
        )
        network.add_node(node)
        cell_to_node[(r, c)] = node_id
        node_id_counter += 1

    # Connect nodes: find nearest downstream node for each
    link_id_counter = 0
    node_cells = list(cell_to_node.keys())

    for r, c in node_cells:
        from_id = cell_to_node[(r, c)]
        from_node = network.nodes[from_id]

        # Find nearest downstream node (higher accumulation, lower elevation)
        best_to = None
        best_dist = float("inf")

        for r2, c2 in node_cells:
            if (r2, c2) == (r, c):
                continue
            to_id = cell_to_node[(r2, c2)]
            to_node = network.nodes[to_id]

            # Must be lower elevation
            if (to_node.ground_elevation_m or 0) >= (from_node.ground_elevation_m or 0):
                continue

            dist = np.sqrt((r2 - r) ** 2 + (c2 - c) ** 2) * cell_size_m
            if dist < best_dist and dist < spacing_cells * cell_size_m * 2:
                best_dist = dist
                best_to = to_id

        if best_to:
            link_id = f"syn_l_{link_id_counter:04d}"
            link = DrainageLink(
                link_id=link_id,
                city_id=city_id,
                from_node=from_id,
                to_node=best_to,
                link_type=DrainageLinkType.PIPE,
                diameter_m=0.6,  # Assume 600mm default
                length_m=round(best_dist, 1),
                manning_n=0.013,  # Concrete pipe default
                data_quality=DataQuality.ASSUMED,
                attributes={"synthetic": True},
            )
            network.add_link(link)
            link_id_counter += 1

    issues = network.validate()
    logger.info(
        "Synthetic drainage network generated",
        nodes=network.node_count,
        links=network.link_count,
        issues=len(issues),
    )
    return network


def generate_swmm_inp(
    network: DrainageNetwork,
    output_path: Path,
    rain_gauge_name: str = "RG1",
    simulation_hours: float = 6.0,
) -> Path:
    """Generate an EPA SWMM 5.2 .inp file from a drainage network.

    Args:
        network: Drainage network to convert
        output_path: Where to save the .inp file
        rain_gauge_name: Name of the rain gauge to reference
        simulation_hours: Simulation duration in hours

    Returns:
        Path to generated .inp file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []

    # Header
    lines.append("[TITLE]")
    lines.append(f";;Synthetic SWMM network for {network.city_id}")
    lines.append("")

    # Options
    lines.append("[OPTIONS]")
    lines.append("FLOW_UNITS           CMS")
    lines.append("INFILTRATION         HORTON")
    lines.append("FLOW_ROUTING         DYNWAVE")
    lines.append("LINK_OFFSETS         DEPTH")
    lines.append("FORCE_MAIN_EQUATION  H-W")
    lines.append(f"START_DATE           01/01/2024")
    lines.append(f"START_TIME           00:00:00")
    lines.append(f"END_DATE             01/01/2024")
    end_h = int(simulation_hours)
    end_m = int((simulation_hours - end_h) * 60)
    lines.append(f"END_TIME             {end_h:02d}:{end_m:02d}:00")
    lines.append("REPORT_STEP          00:05:00")
    lines.append("WET_STEP             00:00:30")
    lines.append("DRY_STEP             01:00:00")
    lines.append("ROUTING_STEP         00:00:10")
    lines.append("")

    # Junctions
    lines.append("[JUNCTIONS]")
    lines.append(";;Name           Elevation   MaxDepth    InitDepth   SurDepth    Aponded")
    for node in network.nodes.values():
        if node.node_type == DrainageNodeType.OUTFALL:
            continue
        inv = node.invert_elevation_m or 0.0
        gnd = node.ground_elevation_m or (inv + 2.0)
        max_depth = gnd - inv
        lines.append(
            f"{node.node_id:<16s} {inv:>11.3f} {max_depth:>11.3f} "
            f"{'0.000':>11s} {'0.000':>11s} {'0':>11s}"
        )
    lines.append("")

    # Outfalls
    lines.append("[OUTFALLS]")
    lines.append(";;Name           Elevation   Type        Stage Data")
    for node in network.nodes.values():
        if node.node_type == DrainageNodeType.OUTFALL:
            inv = node.invert_elevation_m or 0.0
            lines.append(f"{node.node_id:<16s} {inv:>11.3f} FREE")
    lines.append("")

    # Conduits
    lines.append("[CONDUITS]")
    lines.append(";;Name           From Node        To Node          Length      Roughness   InOffset    OutOffset")
    for link in network.links.values():
        length = link.length_m or 100.0
        manning = link.manning_n or 0.013
        lines.append(
            f"{link.link_id:<16s} {link.from_node:<16s} {link.to_node:<16s} "
            f"{length:>11.1f} {manning:>11.4f} {'0':>11s} {'0':>11s}"
        )
    lines.append("")

    # Cross-sections
    lines.append("[XSECTIONS]")
    lines.append(";;Link           Shape        Geom1       Geom2       Geom3       Geom4")
    for link in network.links.values():
        diameter = link.diameter_m or 0.6
        lines.append(
            f"{link.link_id:<16s} {'CIRCULAR':<12s} {diameter:>11.3f} "
            f"{'0':>11s} {'0':>11s} {'0':>11s}"
        )
    lines.append("")

    # Write file
    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    logger.info(
        "SWMM .inp file generated",
        path=str(output_path),
        junctions=sum(1 for n in network.nodes.values() if n.node_type != DrainageNodeType.OUTFALL),
        outfalls=len(network.get_outfalls()),
        conduits=network.link_count,
    )
    return output_path
