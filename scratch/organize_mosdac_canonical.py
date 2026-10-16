import shutil
from pathlib import Path
import json

AUDIT_JSON = Path("data/metadata/mosdac_insat_audit_report.json")
BASE_INPUT = Path("e:/urban/sih/urban-flood-nowcasting/MOSDAC_INSAT_DATA")
BASE_OUTPUT = Path("data/processed/rainfall/insat3dr")

with open(AUDIT_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)

records = data["records"]
print(f"Total records to organize: {len(records)}")

copied = 0
for r in records:
    prod = r["product"]
    year = str(r["year"])
    dest_dir = BASE_OUTPUT / prod / year
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    src_file = BASE_INPUT / r["relative_path"]
    dest_file = dest_dir / r["file_name"]
    
    if not dest_file.exists() or dest_file.stat().st_size != r["file_size_bytes"]:
        shutil.copy2(src_file, dest_file)
        copied += 1

print(f"Canonical copy complete. Copied {copied} files.")
for p in ["HEM", "IMC"]:
    for y in ["2024", "2025"]:
        ydir = BASE_OUTPUT / p / y
        if ydir.exists():
            cnt = len(list(ydir.glob("*.tif")))
            print(f"  {p}/{y}: {cnt} files ({sum(f.stat().st_size for f in ydir.glob('*.tif')):,} bytes)")
