import re
from datetime import datetime, timezone
from pathlib import Path

base_dir = Path("e:/urban/sih/urban-flood-nowcasting/MOSDAC_INSAT_DATA")
tif_files = list(base_dir.rglob("*.tif"))

pattern = re.compile(r"3RIMG_(\d{2})([A-Z]{3})(\d{4})_(\d{2})(\d{2})_L2B_(HEM|IMC)", re.IGNORECASE)

months = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12
}

parsed = []
failed = []

for f in tif_files:
    m = pattern.search(f.name)
    if m:
        day, mon_str, year, hr, minute, prod = m.groups()
        mon = months.get(mon_str.upper())
        if mon:
            dt = datetime(int(year), mon, int(day), int(hr), int(minute), tzinfo=timezone.utc)
            parsed.append((f, prod.upper(), dt))
        else:
            failed.append((f, "invalid month"))
    else:
        failed.append((f, "no regex match"))

print(f"Total files: {len(tif_files)}")
print(f"Parsed datetimes: {len(parsed)}")
print(f"Failed: {len(failed)}")

# Check min/max datetime per product
for prod in ["HEM", "IMC"]:
    p_dates = [dt for _, p, dt in parsed if p == prod]
    if p_dates:
        print(f"\nProduct {prod}:")
        print(f"  Count: {len(p_dates)}")
        print(f"  Earliest: {min(p_dates).isoformat()}")
        print(f"  Latest:   {max(p_dates).isoformat()}")
