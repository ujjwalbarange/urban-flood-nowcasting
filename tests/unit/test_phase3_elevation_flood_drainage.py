"""Unit and integration tests for Phase 3:
- Copernicus GLO-30 DEM elevation service and endpoints
- 2D flood depth raster headers and status contracts
- MSDI v1.0 synthetic drainage generation and provenance
- Drainage network validator
- Verified vs synthetic dataset separation
- Zero-mock policy compliance
"""

import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from services.api.main import app
from services.terrain.elevation_service import (
    lookup_elevation,
    get_elevation_metadata,
    render_elevation_raster,
)
from services.drainage.validator import DrainageNetworkValidator
from services.drainage.synthetic_generator import MSDIGenerator

client = TestClient(app)


class TestCopernicusElevation:
    """Validate Copernicus GLO-30 DEM foundation."""

    def test_elevation_metadata(self):
        meta = get_elevation_metadata()
        assert meta["crs"] == "EPSG:4326"
        assert meta["units"] == "metres"
        assert "EGM96" in meta["vertical_datum"]
        assert meta["rows"] == 1800
        assert meta["cols"] == 1620
        assert meta["min_elevation_m"] < 0.0  # Bathymetric coastal depression
        assert meta["max_elevation_m"] > 400.0  # SGNP summits

        assert meta["west"] == pytest.approx(72.65, 0.01)
        assert meta["east"] == pytest.approx(73.10, 0.01)
        assert meta["south"] == pytest.approx(18.85, 0.01)
        assert meta["north"] == pytest.approx(19.35, 0.01)

    def test_elevation_point_lookup_inside_coverage(self):
        # BMC HQ / CST area: ~18.94N, 72.835E
        res = lookup_elevation(18.9400, 72.8350)
        assert res is not None
        assert isinstance(res, dict)
        elev = res["elevation_m"]
        assert 5.0 <= elev <= 25.0, f"Expected realistic BMC HQ elevation, got {elev}"
        assert res["units"] == "metres"
        assert "EGM96" in res["vertical_datum"]

        # Low-lying Kurla depression: ~19.068N, 72.883E
        kurla_res = lookup_elevation(19.068, 72.883)
        assert kurla_res is not None
        kurla_elev = kurla_res["elevation_m"]
        assert 2.0 <= kurla_elev <= 12.0, f"Expected low-lying Kurla elevation, got {kurla_elev}"

    def test_elevation_point_lookup_outside_coverage(self):
        # Coordinates outside Mumbai bounding box must return None (never fabricated zero)
        out_elev = lookup_elevation(28.6139, 77.2090)  # New Delhi
        assert out_elev is None, "Expected None outside coverage to uphold zero-mock policy"

    def test_elevation_raster_generation(self):
        png_bytes, headers = render_elevation_raster()
        assert len(png_bytes) > 50000, "Expected non-trivial PNG raster stream"
        assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n", "Expected valid PNG magic bytes"
        assert float(headers["X-Georef-MinLat"]) < float(headers["X-Georef-MaxLat"])
        assert float(headers["X-Georef-MinLon"]) < float(headers["X-Georef-MaxLon"])
        assert headers["X-Elevation-Units"] == "metres"

    def test_elevation_endpoints(self):
        # Metadata endpoint
        resp = client.get("/api/v1/geodata/elevation/metadata")
        assert resp.status_code == 200
        data = resp.json()
        assert data["crs"] == "EPSG:4326"
        assert data["units"] == "metres"

        # Point lookup endpoint
        pt_resp = client.get("/api/v1/geodata/elevation/point?lat=19.076&lon=72.877")
        assert pt_resp.status_code == 200
        pt_data = pt_resp.json()
        assert "elevation_m" in pt_data
        assert pt_data["units"] == "metres"
        assert isinstance(pt_data["elevation_m"], (int, float))

        # Raster endpoint
        rast_resp = client.get("/api/v1/geodata/elevation/raster.png")
        assert rast_resp.status_code == 200
        assert rast_resp.headers["content-type"] == "image/png"
        assert "X-Georef-MinLat" in rast_resp.headers
        assert "X-Georef-MaxLat" in rast_resp.headers


class TestFloodDepthPipeline:
    """Validate real flood-depth raster headers, units, and status contracts."""

    def test_nowcast_status_contract(self):
        resp = client.get("/api/v1/nowcast/latest/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "available" in data
        assert "status" in data
        if data["available"]:
            assert data["crs"] == "EPSG:4326"
            assert data["units"] == "metres"
        else:
            assert "unavailable" in data["status"] or data["status"] == "unavailable"

    def test_nowcast_raster_headers_or_clean_empty(self):
        resp = client.get("/api/v1/nowcast/latest/raster.png")
        if resp.status_code == 200:
            assert resp.headers["content-type"] == "image/png"
            assert resp.headers.get("X-Depth-Units") == "metres"
            assert resp.headers.get("X-CRS") == "EPSG:4326"
            assert "X-Georef-MinLat" in resp.headers
        else:
            # If no simulation has run, must be 204 No Content
            assert resp.status_code == 204


class TestSyntheticDrainageAndValidation:
    """Validate MSDI synthetic drainage generation, validator rules, and zero-mock separation."""

    def test_synthetic_drainage_dataset_exists_and_validated(self):
        geojson_path = Path("data/cities/mumbai/synthetic_drainage.geojson")
        assert geojson_path.exists(), "synthetic_drainage.geojson must be generated"

        validator = DrainageNetworkValidator(geojson_path)
        report = validator.validate_all()

        assert report["is_valid"] is True, f"Validation failed: {report}"
        assert report["total_features"] > 1000
        assert report["id_validation"]["valid"] is True
        assert report["geometry_validation"]["valid"] is True
        assert report["slope_validation"]["valid"] is True
        assert report["provenance_validation"]["valid"] is True

    def test_synthetic_provenance_integrity(self):
        geojson_path = Path("data/cities/mumbai/synthetic_drainage.geojson")
        validator = DrainageNetworkValidator(geojson_path)
        report = validator.validate_all()

        # 100% of synthetic features must be explicitly marked synthetic
        prov = report["provenance_validation"]
        assert prov["valid"] is True
        assert prov["non_synthetic_count"] == 0
        assert prov["missing_provenance_count"] == 0

    def test_verified_vs_synthetic_api_separation(self):
        # Verified BRIMSTOWAD master drainage
        ver_resp = client.get("/api/v1/drainage/verified")
        assert ver_resp.status_code == 200
        ver_data = ver_resp.json()
        assert "BRIMSTOWAD" in ver_data["source"]
        for f in ver_data["features"]:
            assert "verified" in f["properties"]["provenance"] or f["properties"]["provenance"] in ["verified", "imported", "verified_brimstowad"]

        # Synthetic MSDI drainage
        syn_resp = client.get("/api/v1/drainage/synthetic")
        assert syn_resp.status_code == 200
        syn_data = syn_resp.json()
        assert syn_data["provenance"] == "synthetic"
        assert "MSDI" in syn_data["generator"]
        for f in syn_data["features"]:
            assert f["properties"]["provenance"] == "synthetic"
            assert "assumed_parameters" in f["properties"]

        # Verify no ID collisions between verified and synthetic
        ver_ids = {f.get("id") or f["properties"].get("link_id") for f in ver_data["features"]}
        syn_ids = {f.get("id") or f["properties"].get("link_id") or f["properties"].get("node_id") for f in syn_data["features"]}
        assert ver_ids.isdisjoint(syn_ids), "Verified and synthetic feature IDs must never collide"

    def test_drainage_validation_report_endpoint(self):
        resp = client.get("/api/v1/drainage/validation-report")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_valid"] is True
        assert data["total_features"] > 1000
        assert data["id_validation"]["valid"] is True
        assert data["geometry_validation"]["valid"] is True
