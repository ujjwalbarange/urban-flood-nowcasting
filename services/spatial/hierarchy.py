"""Dynamic subarea hierarchy and topological neighbor discovery engine for MUFNS.

Discovers subareas from GIS datasets dynamically without hardcoded IDs, names, or counts.
Supports multi-level parent-child relationships (City -> Ward -> Subarea -> Child Subdivisions).
Calculates spatial adjacency and topological neighbors on-the-fly using exact Shapely geometries.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from shapely.geometry import shape, mapping, Polygon, MultiPolygon, Point
from shapely.ops import unary_union
import structlog

logger = structlog.get_logger()

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SUBAREAS_PATH = _PROJECT_ROOT / "data" / "cities" / "mumbai" / "subareas.geojson"


class SubareaHierarchyEngine:
    """Dynamic spatial hierarchy and topological neighbor resolution engine."""

    def __init__(self, geojson_path: Optional[Path] = None):
        self.path = geojson_path or DEFAULT_SUBAREAS_PATH
        self._subareas: Dict[str, Dict[str, Any]] = {}
        self._geometries: Dict[str, Polygon | MultiPolygon] = {}
        self._ward_index: Dict[str, List[str]] = {}
        self._loaded = False
        self._load_and_index()

    def _load_and_index(self) -> None:
        """Dynamically load and index all subareas from GeoJSON."""
        if not self.path.exists():
            logger.warning("Subareas GeoJSON not found", path=str(self.path))
            return

        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)

        features = data.get("features", [])
        self._subareas.clear()
        self._geometries.clear()
        self._ward_index.clear()

        for feat in features:
            props = feat.get("properties", {})
            subarea_id = feat.get("id") or props.get("subarea_id") or props.get("id")
            if not subarea_id:
                continue

            subarea_id = str(subarea_id)
            geom_raw = feat.get("geometry")
            if not geom_raw:
                continue

            geom = shape(geom_raw)
            if not geom.is_valid:
                geom = geom.buffer(0)  # repair slight topological self-intersections

            self._subareas[subarea_id] = {
                "subarea_id": subarea_id,
                "name": props.get("subarea_name") or props.get("name") or f"Subarea {subarea_id}",
                "parent_ward_id": props.get("parent_ward_id") or props.get("ward_id") or "UNKNOWN",
                "parent_ward_name": props.get("parent_ward_name") or props.get("ward_name") or "",
                "zone": props.get("zone", "Greater Mumbai"),
                "area_sq_km": props.get("subarea_area_sq_km") or round(geom.area * 110.57 * 104.64, 3),
                "centroid": [geom.centroid.x, geom.centroid.y],
                "bounds": {
                    "min_lon": geom.bounds[0],
                    "min_lat": geom.bounds[1],
                    "max_lon": geom.bounds[2],
                    "max_lat": geom.bounds[3],
                },
                "properties": props,
                "geometry": mapping(geom),
            }
            self._geometries[subarea_id] = geom

            ward_id = self._subareas[subarea_id]["parent_ward_id"]
            if ward_id not in self._ward_index:
                self._ward_index[ward_id] = []
            self._ward_index[ward_id].append(subarea_id)

        self._loaded = True
        logger.info(
            "Subarea hierarchy loaded",
            total_subareas=len(self._subareas),
            total_wards=len(self._ward_index),
        )

    def reload(self) -> None:
        """Force reload from disk (used when spatial data is subdivided or updated)."""
        self._load_and_index()

    def list_subareas(self, ward_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all discovered subareas with hierarchy, bounds, and parent wards."""
        results = []
        for s_id, s_data in self._subareas.items():
            if ward_filter and s_data["parent_ward_id"] != ward_filter.upper():
                continue
            results.append({
                "subarea_id": s_id,
                "name": s_data["name"],
                "parent_ward_id": s_data["parent_ward_id"],
                "parent_ward_name": s_data["parent_ward_name"],
                "area_sq_km": s_data["area_sq_km"],
                "centroid": s_data["centroid"],
                "bounds": s_data["bounds"],
            })
        return sorted(results, key=lambda x: (x["parent_ward_id"], x["subarea_id"]))

    def get_subarea(self, subarea_id: str) -> Optional[Dict[str, Any]]:
        """Get full details and geometry for a specific subarea."""
        return self._subareas.get(subarea_id)

    def get_neighbors(
        self,
        subarea_id: str,
        buffer_degrees: float = 0.008,  # ~850 meters buffer context
    ) -> List[Dict[str, Any]]:
        """Identify topological neighboring subareas using exact spatial geometry.

        Returns subareas that directly touch, overlap, or fall within the context buffer.
        """
        geom = self._geometries.get(subarea_id)
        if geom is None:
            return []

        search_envelope = geom.buffer(buffer_degrees)
        neighbors = []

        for other_id, other_geom in self._geometries.items():
            if other_id == subarea_id:
                continue

            # Check if neighbor touches boundary directly or intersects the context envelope
            is_touching = geom.touches(other_geom)
            is_within_context = search_envelope.intersects(other_geom)

            if is_touching or is_within_context:
                shared_length_m = 0.0
                if is_touching:
                    try:
                        inter = geom.intersection(other_geom)
                        if inter.geom_type in ("LineString", "MultiLineString"):
                            # Approximate shared boundary length in meters
                            shared_length_m = round(inter.length * 111000.0, 1)
                    except Exception:
                        pass

                other_meta = self._subareas[other_id]
                neighbors.append({
                    "subarea_id": other_id,
                    "neighbor_subarea_id": other_id,
                    "name": other_meta["name"],
                    "parent_ward_id": other_meta["parent_ward_id"],
                    "is_touching": is_touching,
                    "shared_boundary_length_m": shared_length_m,
                    "shared_boundary_length_meters": shared_length_m,
                    "centroid": other_meta["centroid"],
                    "bounds": other_meta["bounds"],
                    "geometry": other_meta["geometry"],
                })

        # Sort: directly touching neighbors first, then by proximity
        return sorted(neighbors, key=lambda n: (not n["is_touching"], -n["shared_boundary_length_m"]))

    def get_context_bounds(
        self,
        subarea_id: str,
        include_neighbors: bool = True,
        margin_factor: float = 0.20,
    ) -> Optional[Dict[str, float]]:
        """Compute spatial bounding box encompassing the subarea and its surrounding context."""
        geom = self._geometries.get(subarea_id)
        if geom is None:
            return None

        if include_neighbors:
            neighbor_geoms = [
                self._geometries[n["subarea_id"]]
                for n in self.get_neighbors(subarea_id)
                if n["subarea_id"] in self._geometries
            ]
            all_geoms = [geom] + neighbor_geoms
            combined = unary_union(all_geoms)
            minx, miny, maxx, maxy = combined.bounds
        else:
            minx, miny, maxx, maxy = geom.bounds

        dx = maxx - minx
        dy = maxy - miny
        return {
            "min_lon": round(minx - dx * margin_factor, 5),
            "min_lat": round(miny - dy * margin_factor, 5),
            "max_lon": round(maxx + dx * margin_factor, 5),
            "max_lat": round(maxy + dy * margin_factor, 5),
        }

    def validate_hierarchy(self) -> Dict[str, Any]:
        """Perform topological validation across the subarea dataset."""
        total = len(self._subareas)
        duplicate_ids = len(self._subareas) != len(self._geometries)
        invalid_geoms = [s_id for s_id, g in self._geometries.items() if not g.is_valid]

        return {
            "is_valid": len(invalid_geoms) == 0 and not duplicate_ids,
            "total_subareas": total,
            "total_parent_wards": len(self._ward_index),
            "invalid_geometry_count": len(invalid_geoms),
            "invalid_geometries": invalid_geoms,
            "duplicate_ids": duplicate_ids,
        }


# Singleton instance
_hierarchy_engine: Optional[SubareaHierarchyEngine] = None


def get_hierarchy_engine() -> SubareaHierarchyEngine:
    """Get or initialize singleton hierarchy engine."""
    global _hierarchy_engine
    if _hierarchy_engine is None:
        _hierarchy_engine = SubareaHierarchyEngine()
    return _hierarchy_engine
