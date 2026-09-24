from pathlib import Path

import httpx
import pytest

from services.ingestion import dem


class _Response:
    status_code = 200
    content = b"II*\x00" + b"\x00" * 12


class _Client:
    params = None

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, params):
        type(self).params = params
        return _Response()


@pytest.mark.asyncio
async def test_download_requires_key_before_network_or_file_creation(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENTOPOGRAPHY_API_KEY", raising=False)
    output = tmp_path / "dem.tif"

    with pytest.raises(ValueError, match="OPENTOPOGRAPHY_API_KEY"):
        await dem.download_copernicus_dem(72.65, 18.85, 73.10, 19.35, output)

    assert not output.exists()


@pytest.mark.asyncio
async def test_download_uses_key_and_atomically_writes_geotiff(tmp_path, monkeypatch):
    monkeypatch.setattr(dem.httpx, "AsyncClient", _Client)
    output = tmp_path / "dem.tif"

    result = await dem.download_copernicus_dem(
        72.65, 18.85, 73.10, 19.35, output, api_key="test-key"
    )

    assert result == output
    assert output.read_bytes() == _Response.content
    assert _Client.params["API_Key"] == "test-key"
    assert _Client.params["demtype"] == "COP30"
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.asyncio
async def test_download_rejects_invalid_bbox_and_non_tiff_response(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="bounding box"):
        await dem.download_copernicus_dem(
            73.10, 18.85, 72.65, 19.35, tmp_path / "invalid.tif", api_key="test-key"
        )

    class HtmlResponse(_Response):
        content = b"<html>error</html>"

    class HtmlClient(_Client):
        async def get(self, url, params):
            return HtmlResponse()

    monkeypatch.setattr(dem.httpx, "AsyncClient", HtmlClient)
    output = tmp_path / "error.tif"
    with pytest.raises(ValueError, match="not a GeoTIFF"):
        await dem.download_copernicus_dem(
            72.65, 18.85, 73.10, 19.35, output, api_key="test-key"
        )
    assert not output.exists()


@pytest.mark.asyncio
async def test_download_hides_credentials_in_connection_errors(tmp_path, monkeypatch):
    class FailingClient(_Client):
        async def get(self, url, params):
            request = httpx.Request("GET", f"{url}?API_Key={params['API_Key']}")
            raise httpx.ConnectError("connection failed", request=request)

    monkeypatch.setattr(dem.httpx, "AsyncClient", FailingClient)

    with pytest.raises(RuntimeError, match="details were withheld") as exc:
        await dem.download_copernicus_dem(
            72.65, 18.85, 73.10, 19.35, tmp_path / "dem.tif", api_key="secret-test-key"
        )
    assert "secret-test-key" not in str(exc.value)


def test_copernicus_dem_loader_and_geojson_export():
    import numpy as np
    from services.terrain.dem_loader import get_catchment_dem, depth_grid_to_geojson

    grid, georef = get_catchment_dem("hindmata_dadar", max_dim=30)
    assert isinstance(grid, np.ndarray)
    assert grid.ndim == 2
    assert grid.shape[0] > 0 and grid.shape[1] > 0
    assert float(grid.min()) >= 0.0
    assert float(grid.max()) < 1000.0  # Mumbai topography is well under 1000m
    assert georef["region_key"] == "hindmata_dadar"

    # Test depth grid to geojson
    test_depth = np.zeros_like(grid)
    test_depth[0, 0] = 0.55  # 55cm water depth
    geojson = depth_grid_to_geojson(test_depth, georef, min_depth_m=0.1)

    assert geojson["type"] == "FeatureCollection"
    assert geojson["feature_count"] == 1
    feature = geojson["features"][0]
    assert feature["geometry"]["type"] == "Polygon"
    assert feature["properties"]["water_depth_m"] == 0.55
    assert feature["properties"]["severity"] == "high"

