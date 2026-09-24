# Open-Meteo Historical Weather API (ERA5 / ERA5-Land)

**Product name:** Historical Weather API / Archive API
**Product ID:** N/A (no product ID system; single archive endpoint)
**API endpoint:** `https://archive-api.open-meteo.com/v1/archive`
**Authentication:** None required (keyless, free for non-commercial use; commercial use should review https://open-meteo.com/en/pricing)
**Spatial resolution:** ~9km (ERA5-Land) or ~25-31km (ERA5), model-dependent, auto-selected per variable
**Temporal resolution:** hourly (source), aggregable server-side to daily
**Coverage:** global, 1940-present

**Example API request** (Mumbai, daily precipitation sum, 2015-2025):
```
https://archive-api.open-meteo.com/v1/archive?latitude=19.0760&longitude=72.8777&start_date=2015-01-01&end_date=2025-12-31&daily=precipitation_sum&timezone=Asia%2FKolkata
```

**Example API request** (hourly precipitation, single monsoon month):
```
https://archive-api.open-meteo.com/v1/archive?latitude=19.0760&longitude=72.8777&start_date=2024-07-01&end_date=2024-07-31&hourly=precipitation&timezone=Asia%2FKolkata
```

**Example response/download procedure:**
1. GET the URL above (browser, curl, or `scripts/download_rainfall.py` in this package).
2. Response is JSON: `{"latitude":..., "longitude":..., "hourly": {"time": [...], "precipitation": [...]}}`.
3. Parse into CSV/Parquet with pandas: `pd.DataFrame(resp.json()["hourly"])`.
4. Repeat for multiple points across Mumbai's wards to approximate spatial variation (single-point queries are cheap and free).

**License:** Open-Meteo data is CC-BY 4.0; underlying ECMWF ERA5/ERA5-Land data is freely available under the Copernicus Climate Change Service (C3S) license (free, open, attribution required).

**Docs:** https://open-meteo.com/en/docs/historical-weather-api
