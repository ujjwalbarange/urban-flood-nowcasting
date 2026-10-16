import os
import json
import csv
from pathlib import Path

# Load raw inventory from previous audit
with open('scratch/inventory_raw.json', 'r', encoding='utf-8') as f:
    raw_inv = json.load(f)

# Also inspect all metadata.json files in mumbai_flood_data_package and mumbai_flood_data
meta_files = list(Path('.').glob('**/metadata.json'))
metadata_dict = {}
for mf in meta_files:
    try:
        with open(mf, 'r', encoding='utf-8') as f:
            data = json.load(f)
            metadata_dict[str(mf)] = data
    except Exception as e:
        pass

print(f"Loaded {len(raw_inv)} files from inventory and {len(metadata_dict)} metadata files.")
