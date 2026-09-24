# Auxiliary APIs for Urban Flood Nowcasting

## 1. OpenStreetMap Overpass API
- **Endpoint**: `https://overpass-api.de/api/interpreter`
- **Use Case**: Downloading vector road centerlines, bridges, culverts, building polygons, and drainage ditches.
- **Bounding Box Query for Mumbai**:
  ```text
  [out:json][timeout:180][bbox:18.88,72.74,19.32,73.08];
  (
    way["highway"~"motorway|trunk|primary|secondary|tertiary"];
    way["waterway"~"river|canal|drain"];
  );
  out body;
  >;
  out skel qt;
  ```

## 2. AWS Registry of Open Data (Copernicus GLO-30 DEM)
- **Bucket**: `s3://copernicus-dem-30m/`
- **HTTPS Gateway**: `https://copernicus-dem-30m.s3.amazonaws.com/`
- **Access Policy**: Free, anonymous public read (No AWS credentials or login required).
- **Mumbai Tiles**:
  - `Copernicus_DSM_COG_10_N18_00_E072_00_DEM/Copernicus_DSM_COG_10_N18_00_E072_00_DEM.tif`
  - `Copernicus_DSM_COG_10_N19_00_E072_00_DEM/Copernicus_DSM_COG_10_N19_00_E072_00_DEM.tif`

## 3. Microsoft Planetary Computer / ESA WorldCover
- **STAC API**: `https://planetarycomputer.microsoft.com/api/stac/v1`
- **Collection**: `esa-worldcover`
- **Tile ID**: `ESA_WorldCover_10m_2021_v200_N18E072_MAP.tif`
- **Access**: Free public HTTPS download via Azure Blob Storage.

## 4. INCOIS Ocean State & Tidal Telemetry API
- **Endpoint**: `https://incois.gov.in/tides/TidesService`
- **Parameters**: `port_code=BOM&interval=60&format=json`
- **Role**: Provides dynamic water level boundary conditions for seaward outfalls.
