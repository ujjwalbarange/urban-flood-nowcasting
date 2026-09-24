"""Flood-aware evacuation routing — Dijkstra with depth-dependent passability.

Routes are computed on the road network graph where edge weights
are modified by flood depth at each road segment:

    effective_speed = base_speed * passability_factor(flood_depth)

Passability policy (based on research literature):
    depth < 0.15m: passable on foot, passable by car
    depth 0.15-0.30m: passable on foot, caution for car
    depth 0.30-0.50m: difficult on foot, impassable for car
    depth > 0.50m: impassable for all

Vehicle profiles adjust these thresholds:
    - pedestrian: lower thresholds
    - car: moderate thresholds
    - emergency_vehicle: highest thresholds (trucks, rescue)
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import structlog

logger = structlog.get_logger()


class VehicleProfile(str, Enum):
    PEDESTRIAN = "pedestrian"
    CAR = "car"
    EMERGENCY = "emergency_vehicle"


class Passability(str, Enum):
    CLEAR = "clear"           # No flood impact
    CAUTION = "caution"       # Reduced speed
    DIFFICULT = "difficult"   # Major speed reduction
    IMPASSABLE = "impassable" # Cannot pass


@dataclass
class PassabilityThresholds:
    """Flood depth thresholds for passability classification."""

    caution_m: float
    difficult_m: float
    impassable_m: float

    def classify(self, depth_m: float) -> Passability:
        if depth_m < self.caution_m:
            return Passability.CLEAR
        elif depth_m < self.difficult_m:
            return Passability.CAUTION
        elif depth_m < self.impassable_m:
            return Passability.DIFFICULT
        else:
            return Passability.IMPASSABLE

    def speed_factor(self, depth_m: float) -> float:
        """Speed reduction factor (0 to 1) based on flood depth."""
        p = self.classify(depth_m)
        if p == Passability.CLEAR:
            return 1.0
        elif p == Passability.CAUTION:
            return 0.5
        elif p == Passability.DIFFICULT:
            return 0.15
        else:
            return 0.0


# Standard thresholds per vehicle profile
THRESHOLDS = {
    VehicleProfile.PEDESTRIAN: PassabilityThresholds(
        caution_m=0.10, difficult_m=0.25, impassable_m=0.45
    ),
    VehicleProfile.CAR: PassabilityThresholds(
        caution_m=0.15, difficult_m=0.30, impassable_m=0.50
    ),
    VehicleProfile.EMERGENCY: PassabilityThresholds(
        caution_m=0.30, difficult_m=0.50, impassable_m=0.80
    ),
}


@dataclass
class RouteSegment:
    """A segment in a computed route."""

    segment_id: str
    from_node: str
    to_node: str
    length_m: float
    travel_time_s: float
    flood_depth_m: float
    passability: Passability


@dataclass
class RouteResult:
    """Result of a route computation."""

    origin: str
    destination: str
    found: bool
    total_distance_m: float = 0.0
    total_time_s: float = 0.0
    max_flood_depth_m: float = 0.0
    worst_passability: Passability = Passability.CLEAR
    segments: list[RouteSegment] = field(default_factory=list)
    node_path: list[str] = field(default_factory=list)


@dataclass
class RoadEdge:
    """Edge in the road graph."""

    edge_id: str
    from_node: str
    to_node: str
    length_m: float
    speed_kmh: float
    flood_depth_m: float = 0.0


class FloodAwareRouter:
    """Dijkstra-based routing on a flood-depth-weighted road graph."""

    def __init__(
        self,
        vehicle: VehicleProfile = VehicleProfile.CAR,
    ):
        self.vehicle = vehicle
        self.thresholds = THRESHOLDS[vehicle]
        self.adjacency: dict[str, list[RoadEdge]] = {}

    def build_graph(self, edges: list[RoadEdge]) -> None:
        """Build adjacency list from road edges."""
        self.adjacency.clear()
        for edge in edges:
            if edge.from_node not in self.adjacency:
                self.adjacency[edge.from_node] = []
            self.adjacency[edge.from_node].append(edge)

            # If not one-way, add reverse edge
            if edge.to_node not in self.adjacency:
                self.adjacency[edge.to_node] = []
            reverse = RoadEdge(
                edge_id=edge.edge_id + "_rev",
                from_node=edge.to_node,
                to_node=edge.from_node,
                length_m=edge.length_m,
                speed_kmh=edge.speed_kmh,
                flood_depth_m=edge.flood_depth_m,
            )
            self.adjacency[edge.to_node].append(reverse)

    def compute_edge_cost(self, edge: RoadEdge) -> float:
        """Compute traversal cost (time in seconds) for an edge.

        Impassable edges get infinite cost.
        """
        speed_factor = self.thresholds.speed_factor(edge.flood_depth_m)
        if speed_factor <= 0:
            return float("inf")  # Impassable

        effective_speed_ms = (edge.speed_kmh * speed_factor) / 3.6
        if effective_speed_ms < 0.1:
            return float("inf")

        return edge.length_m / effective_speed_ms

    def find_route(self, origin: str, destination: str) -> RouteResult:
        """Find shortest (fastest) flood-aware route using Dijkstra."""
        if origin not in self.adjacency:
            return RouteResult(origin=origin, destination=destination, found=False)

        # Dijkstra
        dist = {origin: 0.0}
        prev: dict[str, tuple[str, RoadEdge]] = {}
        pq = [(0.0, origin)]
        visited = set()

        while pq:
            cost, node = heapq.heappop(pq)
            if node in visited:
                continue
            visited.add(node)

            if node == destination:
                break

            for edge in self.adjacency.get(node, []):
                if edge.to_node in visited:
                    continue
                edge_cost = self.compute_edge_cost(edge)
                if edge_cost == float("inf"):
                    continue

                new_cost = cost + edge_cost
                if new_cost < dist.get(edge.to_node, float("inf")):
                    dist[edge.to_node] = new_cost
                    prev[edge.to_node] = (node, edge)
                    heapq.heappush(pq, (new_cost, edge.to_node))

        if destination not in prev and origin != destination:
            return RouteResult(origin=origin, destination=destination, found=False)

        # Reconstruct path
        path_nodes = [destination]
        segments = []
        current = destination

        while current in prev:
            parent, edge = prev[current]
            passability = self.thresholds.classify(edge.flood_depth_m)
            travel_time = self.compute_edge_cost(edge)
            segments.append(
                RouteSegment(
                    segment_id=edge.edge_id,
                    from_node=parent,
                    to_node=current,
                    length_m=edge.length_m,
                    travel_time_s=travel_time,
                    flood_depth_m=edge.flood_depth_m,
                    passability=passability,
                )
            )
            path_nodes.append(parent)
            current = parent

        segments.reverse()
        path_nodes.reverse()

        total_distance = sum(s.length_m for s in segments)
        total_time = sum(s.travel_time_s for s in segments)
        max_depth = max((s.flood_depth_m for s in segments), default=0.0)

        worst = Passability.CLEAR
        for s in segments:
            if s.passability == Passability.IMPASSABLE:
                worst = Passability.IMPASSABLE
            elif s.passability == Passability.DIFFICULT and worst != Passability.IMPASSABLE:
                worst = Passability.DIFFICULT
            elif s.passability == Passability.CAUTION and worst in (Passability.CLEAR,):
                worst = Passability.CAUTION

        return RouteResult(
            origin=origin,
            destination=destination,
            found=True,
            total_distance_m=round(total_distance, 1),
            total_time_s=round(total_time, 1),
            max_flood_depth_m=round(max_depth, 3),
            worst_passability=worst,
            segments=segments,
            node_path=path_nodes,
        )

    def find_nearest_shelter(
        self,
        origin: str,
        shelter_nodes: list[str],
    ) -> Optional[RouteResult]:
        """Find the nearest reachable shelter from origin.

        Tries all shelters and returns the fastest reachable one.
        """
        best_route = None
        best_time = float("inf")

        for shelter in shelter_nodes:
            route = self.find_route(origin, shelter)
            if route.found and route.total_time_s < best_time:
                best_route = route
                best_time = route.total_time_s

        return best_route
