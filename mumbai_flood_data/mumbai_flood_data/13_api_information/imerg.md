# NASA GPM IMERG

**Product/version (recommended):** GPM_3IMERGDF (IMERG Final Run, Daily aggregate, Version 07), 0.1deg x 0.1deg
**Alternative (sub-daily):** GPM_3IMERGHH (Final Run, 30-minute, V07)
**Spatial resolution:** 0.1deg x 0.1deg (~11km at Mumbai's latitude)
**Temporal resolution:** 30-min (HH) or daily (DF); continuous record 2000-present (TRMM+GPM merged)
**Coverage:** global (quasi-global 60N-60S for the microwave-based estimates)

## Earthdata requirements
1. Free NASA Earthdata Login account: https://urs.earthdata.nasa.gov/users/new (instant, no approval wait)
2. Authorize the GES DISC application under your Earthdata profile (one-time, in-browser step)
3. Generate a `.netrc` file or an Earthdata bearer token for scripted access

## Download / API method
**Option A - GES DISC subset service (recommended for a Mumbai-only extract):**
- Use the "Simple Subset Wizard" or OPeNDAP at https://disc.gsfc.nasa.gov/datasets/GPM_3IMERGDF_07/summary
- Subset to bbox `[72.75, 18.85, 72.98, 19.30]` and the desired date range before downloading (avoids pulling global granules)

**Option B - AWS Open Data (S3, credentialed):**
- Registry: https://registry.opendata.aws/nasa-gpm3imergdf/
- Requires temporary AWS credentials obtained via your Earthdata login token: https://data.gesdisc.earthdata.nasa.gov/s3credentialsREADME

**Option C - Giovanni time-series API (quick point/small-area extraction, good for a first look):**
```
curl -X GET "https://api.giovanni.earthdata.nasa.gov/timeseries?data=GPM_3IMERGDF_07_precipitation&location=[19.0760,72.8777]&time=2015-01-01/2025-12-31" -H "authorizationtoken: YOUR_EARTHDATA_TOKEN"
```

## License
Free and open, no restrictions on use; attribution to NASA/GES DISC requested.

## Recommended scope (per task priority)
Rather than the full 2000-present archive, pull IMERG Final Run daily data for:
1. 26-27 July 2005 (benchmark extreme event, for context/validation against station reports)
2. A handful of recent major Mumbai monsoon flood dates (e.g. 29 Aug 2017, 4 Jul 2019, 6 Jun 2024 - VERIFY exact dates against 08_flood_observations records before pulling)
3. The full 2015-2025 daily series only if storage allows (small: ~1 value/day/point)
