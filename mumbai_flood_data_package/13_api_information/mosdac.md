# ISRO MOSDAC Satellite Products & API Specification

## 1. Product Overview
The Meteorological and Oceanographic Satellite Data Archival Centre (MOSDAC) of the Indian Space Research Organisation (ISRO) archives and disseminates operational data from India's meteorological satellite missions (INSAT-3D, INSAT-3DR, and INSAT-3DS).

For the Mumbai Urban Flood Nowcasting System, the following operational products are of primary utility:

1. **Hydro-Estimator Precipitation (HEG)**:
   - **Product Name**: INSAT-3D/3DR Hydro-Estimator Precipitation Grid
   - **Product ID**: `3DIMG_L2B_HEG` (INSAT-3D) / `3RIMG_L2B_HEG` (INSAT-3DR)
   - **Parameter**: Instantaneous surface rain rate (mm/h) derived from cloud-top brightness temperatures tuned against Indian radar networks.
2. **Quantitative Precipitation Estimation (QPE)**:
   - **Product Name**: INSAT-3D/3DR Multispectral QPE
   - **Product ID**: `3DIMG_L2B_QPE`
   - **Parameter**: Convective and stratiform accumulated precipitation.
3. **RAPID Real-time Visualization & Nowcasting**:
   - **Product Name**: Real-time Analysis of Products & Information Dissemination (RAPID)
   - **Product ID**: `RAPID_RGB_CONV`
   - **Parameter**: High-cadence convective cloud tracking and cloud motion vectors.

## 2. Technical Specifications
- **Sensor**: 6-Channel Meteorological Imager (Visible: 0.55–0.75 µm; Shortwave IR: 1.55–1.70 µm; Mid IR: 3.80–4.00 µm; Thermal IR-1: 10.2–11.3 µm; Thermal IR-2: 11.5–12.5 µm; Water Vapor: 6.50–7.10 µm).
- **Spatial Resolution**:
  - Imager Visible: 1 km x 1 km
  - Thermal IR & Water Vapor: 4 km x 4 km
  - HEG & QPE Level-2B Products: 4 km x 4 km (~0.04° grid)
- **Temporal Resolution**:
  - Individual satellite: 30 minutes
  - Staggered INSAT-3D + INSAT-3DR tandem orbit mode: **15 minutes** (critical for 0–3 hour nowcasting).
- **Coverage**: Full Disk and Sector scans over South Asia and the Indian Ocean (0°N–40°N, 40°E–110°E).
- **Data Formats**: HDF5 (`.h5`), NetCDF-4 (`.nc`), and GeoTIFF (`.tif`).

## 3. Authentication & Access Method
- **Portal**: `https://www.mosdac.gov.in/`
- **Access Policy**: Free for registered Indian researchers, academic institutions, and disaster management organizations.
- **Authentication Protocol**:
  - Web Portal: Requires verified user account (Username/Password with email/SMS authentication).
  - Programmatic API: Uses OAuth2 / Bearer Token or HTTP Basic Authentication over HTTPS.
  - OPeNDAP Server: Direct subsetting via `https://mosdac.gov.in/opendap/`.

## 4. API Endpoints & Request Structure

### 4.1 Product Catalog Search Endpoint
```text
GET https://www.mosdac.gov.in/api/v1/search?product=3DIMG_L2B_HEG&start_time=2024-09-25T00:00:00Z&end_time=2024-09-25T23:59:59Z&bbox=72.74,18.88,73.08,19.32
```

### 4.2 cURL Programmatic Download Example
```bash
# Retrieve file token and download HDF5 subset
curl -X GET "https://www.mosdac.gov.in/api/v1/download/3DIMG_25SEP2024_1100_L2B_HEG_V01R00.h5" \
  -H "Authorization: Bearer YOUR_MOSDAC_API_TOKEN" \
  -H "Accept: application/x-hdf5" \
  -o insat3d_heg_20240925_1100.h5
```

### 4.3 Python Automated Extraction using h5py
```python
import h5py
import numpy as np

def extract_mumbai_rain_rate(hdf5_path):
    with h5py.File(hdf5_path, 'r') as f:
        # Inspect dataset keys
        rain_rate = f['RAIN_RATE'][:] # (rows, cols)
        lat = f['Latitude'][:]
        lon = f['Longitude'][:]
        
        # Bounding box filter for Greater Mumbai
        mask = (lat >= 18.88) & (lat <= 19.32) & (lon >= 72.74) & (lon <= 73.08)
        mumbai_rain = rain_rate[mask]
        print(f"Max Mumbai rainfall rate: {np.nanmax(mumbai_rain):.1f} mm/h")
        return mumbai_rain
```

## 5. Sample Data Artifact
A representative JSON extraction from an operational INSAT-3D HEG product during a heavy monsoon event over Mumbai is stored in:
`07_rainfall/mosdac_samples/insat3d_heg_mumbai_sample_20240925.json`
