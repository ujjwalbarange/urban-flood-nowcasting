"""Load local Mumbai dataset files for development and audit.

File presence and self-declared metadata do not establish source authenticity,
license, completeness, or scientific suitability. Consumers must preserve the
dataset verification state from ``DATA_REQUIRED.md`` and must not describe
these files as verified observations until independent lineage checks pass.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger()

# Resolve data package path relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DATA_PKG = _PROJECT_ROOT / "mumbai_flood_data_package"
# Fallback to nested path if the above doesn't exist
if not _DATA_PKG.exists():
    _DATA_PKG = _PROJECT_ROOT / "mumbai_flood_data" / "mumbai_flood_data"


def _load_geojson(path: Path) -> dict[str, Any]:
    """Load a GeoJSON file and return the parsed dict."""
    if not path.exists():
        logger.warning("GeoJSON file not found", path=str(path))
        return {"type": "FeatureCollection", "features": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_csv(path: Path) -> list[dict[str, str]]:
    """Load a CSV file and return list of row dicts."""
    if not path.exists():
        logger.warning("CSV file not found", path=str(path))
        return []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def _load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file and return the parsed dict."""
    if not path.exists():
        logger.warning("JSON file not found", path=str(path))
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


class MumbaiDataStore:
    """In-memory loader for local Mumbai candidate datasets.

    This class does not validate source lineage and should not be treated as a
    trust boundary. See ``DATA_REQUIRED.md`` for each dataset's audit status.
    """

    def __init__(self, data_root: Optional[Path] = None):
        self._root = data_root or _DATA_PKG
        self._cache: dict[str, Any] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._load_all()
        self._loaded = True

    def _load_all(self) -> None:
        """Load all datasets into memory."""
        root = self._root
        logger.info("Loading Mumbai candidate data package", root=str(root))

        # ── 01: City ──
        self._cache["city_config"] = _load_json(root / "01_city" / "config.json")
        self._cache["city_boundary"] = _load_geojson(root / "01_city" / "mumbai_boundary.geojson")
        self._cache["wards"] = _load_geojson(root / "01_city" / "wards.geojson")
        self._cache["subareas"] = _load_geojson(root / "01_city" / "subareas.geojson")
        if not self._cache["subareas"].get("features"):
            self._cache["subareas"] = _load_geojson(_PROJECT_ROOT / "data" / "cities" / "mumbai" / "subareas.geojson")

        # ── Critical / Emergency Facilities ──
        emerg_fac_path = _PROJECT_ROOT / "data" / "processed" / "critical_infrastructure" / "mumbai_emergency_facilities.geojson"
        self._cache["emergency_facilities"] = _load_geojson(emerg_fac_path)

        # ── 04: Roads ──
        self._cache["roads"] = _load_geojson(root / "04_roads" / "roads.geojson")

        # ── 05: Buildings ──
        self._cache["buildings"] = _load_geojson(root / "05_buildings" / "buildings.geojson")

        # ── 06: Drainage ──
        self._cache["drainage_nodes"] = _load_geojson(root / "06_drainage" / "nodes.geojson")
        self._cache["drainage_links"] = _load_geojson(root / "06_drainage" / "links.geojson")
        self._cache["drainage_outfalls"] = _load_geojson(root / "06_drainage" / "outfalls.geojson")

        # ── 07: Rainfall ──
        self._cache["rainfall_gauges"] = _load_csv(
            root / "07_rainfall" / "gauges" / "hourly_gauge_data_2015_2025.csv"
        )
        self._cache["gauge_stations"] = _load_geojson(
            root / "07_rainfall" / "gauges" / "station_metadata.geojson"
        )
        # Historical events
        hist_dir = root / "07_rainfall" / "historical"
        self._cache["historical_events"] = {}
        if hist_dir.exists():
            for csv_file in sorted(hist_dir.glob("event_*.csv")):
                event_key = csv_file.stem  # e.g. "event_2005_07_26_santacruz_colaba_15min"
                self._cache["historical_events"][event_key] = _load_csv(csv_file)
        # IMERG
        imerg_dir = root / "07_rainfall" / "imerg"
        self._cache["imerg"] = {}
        if imerg_dir.exists():
            for csv_file in imerg_dir.glob("*.csv"):
                self._cache["imerg"][csv_file.stem] = _load_csv(csv_file)
        # MOSDAC
        mosdac_dir = root / "07_rainfall" / "mosdac_samples"
        self._cache["mosdac_samples"] = {}
        if mosdac_dir.exists():
            for json_file in mosdac_dir.glob("*.json"):
                self._cache["mosdac_samples"][json_file.stem] = _load_json(json_file)

        # ── 08: Flood Observations ──
        self._cache["flood_hotspots"] = _load_geojson(
            root / "08_flood_observations" / "flood_points.geojson"
        )
        self._cache["flood_polygons"] = _load_geojson(
            root / "08_flood_observations" / "flood_polygons.geojson"
        )
        # Historical event reports
        events_dir = root / "08_flood_observations" / "historical_events"
        if events_dir.exists():
            bmc_csv = events_dir / "bmc_chronic_spots_inventory.csv"
            if bmc_csv.exists():
                self._cache["bmc_chronic_spots"] = _load_csv(bmc_csv)

        # ── 09: Population ──
        self._cache["population"] = _load_geojson(root / "09_population" / "population.geojson")

        # ── 10: Shelters ──
        self._cache["shelters"] = _load_geojson(root / "10_shelters" / "shelters.geojson")

        # ── 11: Coastal ──
        self._cache["coastline"] = _load_geojson(root / "11_coastal" / "coastline.geojson")
        tide_dir = root / "11_coastal" / "tide"
        if tide_dir.exists():
            for csv_file in tide_dir.glob("*.csv"):
                self._cache[f"tide_{csv_file.stem}"] = _load_csv(csv_file)
            benchmarks = tide_dir / "apollo_bunder_tide_benchmarks.json"
            if benchmarks.exists():
                self._cache["tide_benchmarks"] = _load_json(benchmarks)

        # ── 12: Synthetic Scenarios ──
        synth_dir = root / "12_synthetic" / "rainfall_scenarios"
        self._cache["synthetic_scenarios"] = {}
        if synth_dir.exists():
            for csv_file in sorted(synth_dir.glob("*.csv")):
                self._cache["synthetic_scenarios"][csv_file.stem] = _load_csv(csv_file)

        # Count loaded items
        total_features = 0
        for key, val in self._cache.items():
            if isinstance(val, dict) and "features" in val:
                total_features += len(val["features"])
            elif isinstance(val, list):
                total_features += len(val)

        logger.info(
            "Mumbai data package loaded",
            datasets=len(self._cache),
            total_features=total_features,
            rain_gauge_records=len(self._cache.get("rainfall_gauges", [])),
            historical_events=len(self._cache.get("historical_events", {})),
        )

    # ── Public Accessors ──

    def city_config(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("city_config", {})

    def city_boundary(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("city_boundary", {"type": "FeatureCollection", "features": []})

    def wards(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("wards", {"type": "FeatureCollection", "features": []})

    def subareas(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("subareas", {"type": "FeatureCollection", "features": []})

    def emergency_facilities(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("emergency_facilities", {"type": "FeatureCollection", "features": []})

    def roads(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("roads", {"type": "FeatureCollection", "features": []})

    def buildings(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("buildings", {"type": "FeatureCollection", "features": []})

    def drainage_nodes(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("drainage_nodes", {"type": "FeatureCollection", "features": []})

    def drainage_links(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("drainage_links", {"type": "FeatureCollection", "features": []})

    def drainage_outfalls(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("drainage_outfalls", {"type": "FeatureCollection", "features": []})

    def flood_hotspots(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("flood_hotspots", {"type": "FeatureCollection", "features": []})

    def flood_polygons(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("flood_polygons", {"type": "FeatureCollection", "features": []})

    def shelters(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("shelters", {"type": "FeatureCollection", "features": []})

    def population(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("population", {"type": "FeatureCollection", "features": []})

    def coastline(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("coastline", {"type": "FeatureCollection", "features": []})

    def rainfall_gauges(self) -> list[dict[str, str]]:
        self._ensure_loaded()
        return self._cache.get("rainfall_gauges", [])

    def gauge_stations(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("gauge_stations", {"type": "FeatureCollection", "features": []})

    def historical_events(self) -> dict[str, list[dict[str, str]]]:
        self._ensure_loaded()
        return self._cache.get("historical_events", {})

    def historical_event(self, event_key: str) -> list[dict[str, str]]:
        self._ensure_loaded()
        events = self._cache.get("historical_events", {})
        return events.get(event_key, [])

    def imerg_data(self) -> dict[str, list[dict[str, str]]]:
        self._ensure_loaded()
        return self._cache.get("imerg", {})

    def mosdac_samples(self) -> dict[str, dict[str, Any]]:
        self._ensure_loaded()
        return self._cache.get("mosdac_samples", {})

    def synthetic_scenarios(self) -> dict[str, list[dict[str, str]]]:
        self._ensure_loaded()
        return self._cache.get("synthetic_scenarios", {})

    def tide_data(self) -> list[dict[str, str]]:
        """Return Apollo Bunder tide gauge data for the 2005 event."""
        self._ensure_loaded()
        return self._cache.get(
            "tide_apollo_bunder_hourly_tide_20050725_20050727", []
        )

    def tide_benchmarks(self) -> dict[str, Any]:
        self._ensure_loaded()
        return self._cache.get("tide_benchmarks", {})

    def bmc_chronic_spots(self) -> list[dict[str, str]]:
        self._ensure_loaded()
        return self._cache.get("bmc_chronic_spots", [])


# ── Singleton instance ──
_store: Optional[MumbaiDataStore] = None


def get_data_store() -> MumbaiDataStore:
    """Get the singleton data store instance."""
    global _store
    if _store is None:
        _store = MumbaiDataStore()
    return _store
"""Data services — real Mumbai geospatial data loading and serving."""
