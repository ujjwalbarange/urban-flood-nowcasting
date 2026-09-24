# Open-Meteo Meteorological API Integration Guide

## 1. Overview
Open-Meteo provides free, open-source weather and climate APIs offering high-resolution historical reanalysis (ERA5 & ERA5-Land) and short-term numerical weather prediction (NWP) forecasts.

- **License**: Creative Commons Attribution 4.0 International (CC-BY 4.0). Free for non-commercial and research use without requiring an API key (up to 10,000 calls/day).
- **Spatial Resolution**: ~9 km (ERA5-Land reanalysis), downscaled bilinearly to point coordinates.
- **Temporal Resolution**: Hourly and 15-minute intervals.

## 2. API Endpoints

### 2.1 Historical Reanalysis API (1940 to present)
- **Base URL**: `https://archive-api.open-meteo.com/v1/archive`
- **Use Case**: Extracting multi-year monsoon rainfall (2015–2025) for Mumbai observatories to train hydrodynamic and machine learning surrogate models.

### 2.2 Short-Range Forecast API (0 to 7 days ahead)
- **Base URL**: `https://api.open-meteo.com/v1/forecast`
- **Use Case**: Ingesting forward-looking 0–6 hour rainfall forecasts to drive the real-time flood nowcasting pipeline.

## 3. Query Parameters for Mumbai
| Parameter | Description | Recommended Value for Mumbai |
| :--- | :--- | :--- |
| `latitude` | Decimal latitude | `19.0760` (City Center), `19.1172` (Santacruz), `18.8987` (Colaba) |
| `longitude` | Decimal longitude | `72.8777` (City Center), `72.8561` (Santacruz), `72.8094` (Colaba) |
| `hourly` | Requested weather variables | `precipitation,rain,weather_code,wind_speed_10m,surface_pressure` |
| `minutely_15` | High-frequency precipitation | `precipitation` |
| `timezone` | Timezone formatting | `Asia/Kolkata` or `UTC` |
| `start_date` | Query start date | `YYYY-MM-DD` |
| `end_date` | Query end date | `YYYY-MM-DD` |

## 4. Implementation Code Examples

### 4.1 cURL Request (Historical Santacruz Monsoonal Record)
```bash
curl -G "https://archive-api.open-meteo.com/v1/archive" \
  --data-urlencode "latitude=19.1172" \
  --data-urlencode "longitude=72.8561" \
  --data-urlencode "start_date=2024-06-01" \
  --data-urlencode "end_date=2024-09-30" \
  --data-urlencode "hourly=precipitation,rain,surface_pressure" \
  --data-urlencode "timezone=Asia/Kolkata" \
  -o santacruz_monsoon_2024.json
```

### 4.2 Python Automated Extraction Script
```python
import urllib.parse
import urllib.request
import json
import pandas as pd

params = {
    "latitude": 19.1172,
    "longitude": 72.8561,
    "start_date": "2024-07-01",
    "end_date": "2024-07-31",
    "hourly": "precipitation,rain",
    "timezone": "UTC"
}

url = f"https://archive-api.open-meteo.com/v1/archive?{urllib.parse.urlencode(params)}"
with urllib.request.urlopen(url) as response:
    data = json.loads(response.read().decode())

df = pd.DataFrame({
    "timestamp_utc": data["hourly"]["time"],
    "precipitation_mm": data["hourly"]["precipitation"],
    "rain_mm": data["hourly"]["rain"]
})
print(f"Retrieved {len(df)} hourly records. Total rainfall: {df['precipitation_mm'].sum():.1f} mm")
```
