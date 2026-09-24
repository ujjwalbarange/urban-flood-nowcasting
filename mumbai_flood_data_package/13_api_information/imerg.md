# NASA GPM IMERG Precipitation Product & Earthdata API Guide

## 1. Product Overview
The Integrated Multi-satellitE Retrievals for GPM (IMERG) algorithm combines precipitation estimates from the GPM passive microwave constellation, infrared geosynchronous satellites, and monthly surface rain gauge analyses.

- **Product ID**: `GPM_3IMERGHH` (Half-hourly)
- **Current Version**: V07B (released 2024)
- **Run Types**:
  1. **Early Run**: Latency ~4 hours. Multi-satellite without gauge calibration. Used for near-real-time early warning.
  2. **Late Run**: Latency ~14 hours. Incorporates climatological corrections. Used for operational daily reviews.
  3. **Final Run**: Latency ~3.5 months. Fully calibrated with GPCC ground rain gauges. Used for historical research and model training.
- **Spatial Resolution**: 0.1° x 0.1° (~10 km x 10 km).
- **Temporal Resolution**: 30 minutes (48 files per day).
- **Spatial Extent**: 60°N to 60°S global coverage.
- **License**: NASA Open Data Policy (Free and open worldwide).

## 2. NASA Earthdata Authentication
Access requires a free NASA Earthdata login:
1. Register at: `https://urs.earthdata.nasa.gov/`
2. Under "Applications" -> "Authorized Apps", approve:
   - `NASA GES DISC DATA ARCHIVE`
3. Configure local credentials in `~/.netrc`:
   ```text
   machine urs.earthdata.nasa.gov login YOUR_USERNAME password YOUR_PASSWORD
   ```

## 3. API Endpoints & Access Methods

### 3.1 Direct HTTPS Download (GES DISC Archive)
- **Base URL**: `https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/GPM_3IMERGHH.07/`
- **File Structure**: `YYYY/DOY/3B-HHR.MS.MRG.3IMERG.YYYYMMDD-SXXXXXX-EXXXXXX.XXXX.V07B.HDF5`

### 3.2 OPeNDAP Spatial & Temporal Subsetting Server
OPeNDAP allows extracting only the Mumbai bounding box without downloading the entire global file:
- **OPeNDAP Base**: `https://gpm1.gesdisc.eosdis.nasa.gov/opendap/GPM_L3/GPM_3IMERGHH.07/`
- **Spatial Query Example (Mumbai Bounding Box)**:
  `lat[788:792],lon[2527:2531]` corresponds to Lat 18.8°N–19.4°N, Lon 72.7°E–73.2°E.

### 3.3 Python Extraction Script using earthaccess
```python
import earthaccess
import xarray as xr

# Authenticate using ~/.netrc or interactive prompt
auth = earthaccess.login(strategy="netrc")

# Search for half-hourly IMERG granules over Mumbai
results = earthaccess.search_data(
    short_name="GPM_3IMERGHH",
    version="07",
    bounding_box=(72.74, 18.88, 73.08, 19.32),
    temporal=("2024-07-26", "2024-07-27")
)

print(f"Found {len(results)} IMERG granules.")
# Open directly as remote xarray dataset
files = earthaccess.open(results)
ds = xr.open_dataset(files[0], group="Grid")
rain_rate = ds["precipitationCal"].sel(lat=slice(18.88, 19.32), lon=slice(72.74, 73.08))
print(rain_rate)
```
