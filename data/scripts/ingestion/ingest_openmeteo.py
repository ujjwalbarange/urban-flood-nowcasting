"""Open-Meteo comprehensive weather and rainfall ingestion script.

Extracts all available atmospheric, hydrological, and soil parameters across
Mumbai's 9 monitoring stations:
1. Colaba (South Mumbai)
2. Santacruz (Airport / Central)
3. Dadar (Central Island City)
4. Kurla (Mithi River Basin)
5. Vikhroli (Eastern Suburbs)
6. Bandra (Western Coast)
7. Andheri (Western Suburbs)
8. Borivali (Northern Suburbs)
9. Thane (Northeastern Basin)

Stores:
- Raw JSON responses in data/raw/weather/
- Structured observation tables in data/processed/weather/observations.csv
- Structured forecast tables in data/processed/weather/forecasts.csv (with lead_minutes)
"""

import os
import sys
import json
import csv
import time
from datetime import datetime, timezone
from pathlib import Path
import urllib.request

STATIONS = [
    {"id": "STN_COLABA", "name": "Colaba", "lat": 18.8987, "lon": 72.8094, "ward": "A"},
    {"id": "STN_SANTACRUZ", "name": "Santacruz", "lat": 19.0886, "lon": 72.8679, "ward": "H/E"},
    {"id": "STN_DADAR", "name": "Dadar / Hindmata", "lat": 19.0178, "lon": 72.8478, "ward": "F/N"},
    {"id": "STN_KURLA", "name": "Kurla (Mithi Basin)", "lat": 19.0664, "lon": 72.8789, "ward": "L"},
    {"id": "STN_VIKHROLI", "name": "Vikhroli", "lat": 19.1111, "lon": 72.9278, "ward": "S"},
    {"id": "STN_BANDRA", "name": "Bandra West", "lat": 19.0544, "lon": 72.8402, "ward": "H/W"},
    {"id": "STN_ANDHERI", "name": "Andheri West", "lat": 19.1197, "lon": 72.8464, "ward": "K/W"},
    {"id": "STN_BORIVALI", "name": "Borivali", "lat": 19.2288, "lon": 72.8541, "ward": "R/C"},
    {"id": "STN_THANE", "name": "Thane Outflow", "lat": 19.2183, "lon": 72.9781, "ward": "T"},
]

HOURLY_VARS = [
    "temperature_2m", "relative_humidity_2m", "dew_point_2m", "apparent_temperature",
    "precipitation_probability", "precipitation", "rain", "showers", "weather_code",
    "surface_pressure", "cloud_cover", "visibility", "evapotranspiration",
    "et0_fao_evapotranspiration", "vapour_pressure_deficit", "wind_speed_10m",
    "wind_direction_10m", "wind_gusts_10m", "soil_temperature_0cm", "soil_moisture_0_to_1cm"
]

CURRENT_VARS = [
    "temperature_2m", "relative_humidity_2m", "apparent_temperature", "precipitation",
    "rain", "showers", "weather_code", "cloud_cover", "surface_pressure",
    "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m"
]

UNIT_MAP = {
    "temperature_2m": "°C",
    "apparent_temperature": "°C",
    "dew_point_2m": "°C",
    "soil_temperature_0cm": "°C",
    "relative_humidity_2m": "%",
    "cloud_cover": "%",
    "precipitation_probability": "%",
    "precipitation": "mm",
    "rain": "mm",
    "showers": "mm",
    "evapotranspiration": "mm",
    "et0_fao_evapotranspiration": "mm",
    "surface_pressure": "hPa",
    "visibility": "m",
    "vapour_pressure_deficit": "kPa",
    "wind_speed_10m": "km/h",
    "wind_gusts_10m": "km/h",
    "wind_direction_10m": "degrees",
    "soil_moisture_0_to_1cm": "m³/m³",
    "weather_code": "WMO code"
}

def fetch_station_data(station):
    lat = station["lat"]
    lon = station["lon"]
    current_str = ",".join(CURRENT_VARS)
    hourly_str = ",".join(HOURLY_VARS)
    
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&"
        f"current={current_str}&"
        f"hourly={hourly_str}&"
        f"timezone=Asia/Kolkata&forecast_days=7"
    )
    
    req = urllib.request.Request(url, headers={"User-Agent": "MUFNS-Data-Ingestion/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    print(f"=== INGESTING OPEN-METEO WEATHER FOR {len(STATIONS)} MUMBAI STATIONS ===")
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    now_ts_str = now_utc.strftime("%Y%m%d_%H%M%S")
    
    raw_dir = Path("data/raw/weather")
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    proc_weather_dir = Path("data/processed/weather")
    proc_weather_dir.mkdir(parents=True, exist_ok=True)
    proc_rain_dir = Path("data/processed/rainfall")
    proc_rain_dir.mkdir(parents=True, exist_ok=True)
    
    observations_rows = []
    forecasts_rows = []
    
    for st in STATIONS:
        print(f"Fetching {st['name']} ({st['id']})...")
        try:
            data = fetch_station_data(st)
            
            # Save raw station payload
            st_raw_file = raw_dir / f"openmeteo_{st['id']}_{now_ts_str}.json"
            with open(st_raw_file, "w", encoding="utf-8") as rf:
                json.dump(data, rf, indent=2)
                
            # Process Current Observation
            current = data.get("current", {})
            obs_time = current.get("time")
            for var in CURRENT_VARS:
                val = current.get(var)
                observations_rows.append({
                    "station_id": st["id"],
                    "station_name": st["name"],
                    "latitude": st["lat"],
                    "longitude": st["lon"],
                    "ward": st["ward"],
                    "observation_time": obs_time,
                    "ingested_at": now_iso,
                    "variable": var,
                    "value": val,
                    "unit": UNIT_MAP.get(var, ""),
                    "source": "Open-Meteo",
                    "model": "ECMWF_IFS_DWD_ICON",
                    "quality_flag": "VALID_ESTIMATE" if val is not None else "MISSING"
                })
                
            # Process Hourly Forecasts
            hourly = data.get("hourly", {})
            times = hourly.get("time", [])
            for i, valid_time in enumerate(times):
                try:
                    # Calculate lead minutes relative to current generation time
                    dt_valid = datetime.fromisoformat(valid_time)
                    # Simple lead estimation
                    lead_minutes = i * 60
                except Exception:
                    lead_minutes = i * 60
                    
                for var in HOURLY_VARS:
                    vals = hourly.get(var, [])
                    val = vals[i] if i < len(vals) else None
                    forecasts_rows.append({
                        "station_id": st["id"],
                        "station_name": st["name"],
                        "latitude": st["lat"],
                        "longitude": st["lon"],
                        "ward": st["ward"],
                        "forecast_generated_at": obs_time,
                        "forecast_valid_time": valid_time,
                        "lead_minutes": lead_minutes,
                        "variable": var,
                        "value": val,
                        "unit": UNIT_MAP.get(var, ""),
                        "source": "Open-Meteo",
                        "model": "ECMWF_IFS_DWD_ICON",
                        "quality_flag": "FORECAST" if val is not None else "MISSING"
                    })
            time.sleep(0.2)
        except Exception as e:
            print(f"  Error fetching {st['name']}: {e}")
            
    # Write processed observation CSV
    obs_csv_path = proc_weather_dir / "observations.csv"
    if observations_rows:
        with open(obs_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(observations_rows[0].keys()))
            writer.writeheader()
            writer.writerows(observations_rows)
            
    # Write processed forecast CSV
    fcst_csv_path = proc_weather_dir / "forecasts.csv"
    if forecasts_rows:
        with open(fcst_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(forecasts_rows[0].keys()))
            writer.writeheader()
            writer.writerows(forecasts_rows)
            
    # Write rainfall-specific subsets for immediate hydrodynamic model ingestion
    rain_obs = [r for r in observations_rows if r["variable"] in ["precipitation", "rain", "showers"]]
    rain_fcst = [r for r in forecasts_rows if r["variable"] in ["precipitation", "rain", "showers", "precipitation_probability"]]
    
    with open(proc_rain_dir / "rainfall_observations.csv", "w", newline="", encoding="utf-8") as f:
        if rain_obs:
            writer = csv.DictWriter(f, fieldnames=list(rain_obs[0].keys()))
            writer.writeheader()
            writer.writerows(rain_obs)
            
    with open(proc_rain_dir / "rainfall_forecasts.csv", "w", newline="", encoding="utf-8") as f:
        if rain_fcst:
            writer = csv.DictWriter(f, fieldnames=list(rain_fcst[0].keys()))
            writer.writeheader()
            writer.writerows(rain_fcst)
            
    print(f"Successfully processed:")
    print(f"  - {len(observations_rows)} weather observations -> {obs_csv_path}")
    print(f"  - {len(forecasts_rows)} weather forecasts (up to +168h lead time) -> {fcst_csv_path}")
    print(f"  - {len(rain_obs)} rainfall observations -> {proc_rain_dir / 'rainfall_observations.csv'}")
    print(f"  - {len(rain_fcst)} rainfall forecasts -> {proc_rain_dir / 'rainfall_forecasts.csv'}")

if __name__ == "__main__":
    main()
