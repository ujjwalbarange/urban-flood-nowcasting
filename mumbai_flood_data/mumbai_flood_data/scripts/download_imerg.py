#!/usr/bin/env python3
"""
Template for pulling NASA GPM IMERG Final Run daily precipitation for Mumbai.
Requires a free Earthdata account: https://urs.earthdata.nasa.gov/users/new
Set EARTHDATA_TOKEN as an environment variable (generate at https://urs.earthdata.nasa.gov -> Generate Token).
"""
import os
import requests

TOKEN = os.environ.get("EARTHDATA_TOKEN")
if not TOKEN:
    raise SystemExit("Set EARTHDATA_TOKEN first (free account at urs.earthdata.nasa.gov)")

# Example: Giovanni time-series API for a Mumbai point, daily IMERG precipitation
url = (
    "https://api.giovanni.earthdata.nasa.gov/timeseries"
    "?data=GPM_3IMERGDF_07_precipitation"
    "&location=[19.0760,72.8777]"
    "&time=2015-01-01/2025-12-31"
)
headers = {"authorizationtoken": TOKEN}
r = requests.get(url, headers=headers, timeout=120)
r.raise_for_status()
with open("../07_rainfall/imerg/mumbai_point_daily.json", "w") as f:
    f.write(r.text)
print("Saved ../07_rainfall/imerg/mumbai_point_daily.json")

# For a full spatial subset (not just one point), use the GES DISC Simple Subset Wizard
# or OPeNDAP with your Earthdata .netrc credentials - see 13_api_information/imerg.md.
