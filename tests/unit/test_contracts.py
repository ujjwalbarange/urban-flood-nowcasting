"""Tests for City CRUD API endpoints and contracts."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from services.api.main import app
from packages.contracts.city import BoundingBox, CityCreate, CityResponse


MUMBAI_PAYLOAD = {
    "city_id": "mumbai",
    "name": "Mumbai",
    "state": "Maharashtra",
    "country": "IN",
    "crs_epsg": 32643,
    "cell_size_m": 30.0,
    "bbox": {
        "min_lon": 72.775,
        "min_lat": 18.893,
        "max_lon": 72.985,
        "max_lat": 19.275,
    },
    "timezone": "Asia/Kolkata",
    "config": {"ward_count": 24},
}


class TestBoundingBox:
    """Unit tests for BoundingBox contract."""

    def test_to_wkt_polygon(self):
        bbox = BoundingBox(min_lon=72.0, min_lat=19.0, max_lon=73.0, max_lat=20.0)
        wkt = bbox.to_wkt_polygon()
        assert wkt.startswith("POLYGON((")
        assert "72.0 19.0" in wkt
        assert "73.0 20.0" in wkt

    def test_bbox_validation(self):
        bbox = BoundingBox(min_lon=72.775, min_lat=18.893, max_lon=72.985, max_lat=19.275)
        assert bbox.min_lon < bbox.max_lon
        assert bbox.min_lat < bbox.max_lat


class TestCityCreate:
    """Unit tests for CityCreate contract."""

    def test_valid_mumbai(self):
        city = CityCreate(**MUMBAI_PAYLOAD)
        assert city.city_id == "mumbai"
        assert city.crs_epsg == 32643
        assert city.bbox.min_lon == 72.775

    def test_invalid_city_id(self):
        payload = {**MUMBAI_PAYLOAD, "city_id": "123"}
        with pytest.raises(Exception):
            CityCreate(**payload)

    def test_city_id_pattern(self):
        payload = {**MUMBAI_PAYLOAD, "city_id": "Mumbai"}
        with pytest.raises(Exception):
            CityCreate(**payload)


class TestMassBalance:
    """Unit tests for mass balance closure computation."""

    def test_perfect_closure(self):
        from packages.contracts.flood import MassBalance

        mb = MassBalance(
            total_rainfall_m3=1000.0,
            total_infiltration_m3=200.0,
            total_boundary_outflow_m3=100.0,
            initial_surface_volume_m3=0.0,
            final_surface_volume_m3=700.0,
        )
        error = mb.compute_closure()
        assert error < 0.01  # Near-perfect closure

    def test_closure_error_detection(self):
        from packages.contracts.flood import MassBalance

        mb = MassBalance(
            total_rainfall_m3=1000.0,
            total_infiltration_m3=200.0,
            total_boundary_outflow_m3=100.0,
            initial_surface_volume_m3=0.0,
            final_surface_volume_m3=500.0,  # 200 m3 missing → 20% error
        )
        error = mb.compute_closure()
        assert error > 10.0


class TestProvenance:
    """Unit tests for provenance tracking."""

    def test_provenance_creation(self):
        from packages.contracts.provenance import DataQuality, DataSource, Provenance

        p = Provenance(
            source=DataSource.COPERNICUS_DEM,
            quality=DataQuality.MEASURED,
            processing_method="bilinear_resampling",
        )
        assert p.source == DataSource.COPERNICUS_DEM
        assert p.quality == DataQuality.MEASURED
        assert p.ingested_at is not None
