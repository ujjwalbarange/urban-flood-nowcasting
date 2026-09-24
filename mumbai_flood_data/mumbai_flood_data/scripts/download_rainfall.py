#!/usr/bin/env python3
"""
Pull historical rainfall for Mumbai from Open-Meteo's free, keyless ERA5/ERA5-Land archive API.
Run on a machine with internet access.
"""
import requests
import pandas as pd
import os

OUT_DIR = "../07_rainfall/historical"
os.makedirs(OUT_DIR, exist_ok=True)

# Sample points across Mumbai (rough ward-cluster centroids) - refine using actual ward centroids
# once 01_city/wards.geojson is downloaded.
POINTS = {
    "colaba_south":    (18.9067, 72.8147),
    "dadar_central":   (19.0176, 72.8437),
    "andheri_west":    (19.1197, 72.8464),
    "borivali_north":  (19.2307, 72.8567),
    "mulund_east":     (19.1726, 72.9425),
}

START, END = "2015-01-01", "2025-12-31"

for name, (lat, lon) in POINTS.items():
    url = (
        "https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={START}&end_date={END}"
        "&hourly=precipitation&timezone=Asia%2FKolkata"
    )
    print(f"Fetching {name}...")
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    data = r.json()["hourly"]
    df = pd.DataFrame(data)
    df.to_csv(f"{OUT_DIR}/{name}_hourly_precip_{START}_{END}.csv", index=False)
    print(f"  wrote {len(df)} rows")

print("Done. Each file: timestamp (IST) + precipitation (mm).")
