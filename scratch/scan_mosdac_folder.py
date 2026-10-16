import os
from pathlib import Path

base_dir = Path("e:/urban/sih/urban-flood-nowcasting/MOSDAC_INSAT_DATA")
files = list(base_dir.rglob("*"))
print(f"Total entries found: {len(files)}")

file_list = [f for f in files if f.is_file()]
dir_list = [d for d in files if d.is_dir()]
print(f"Directories: {len(dir_list)}")
print(f"Files: {len(file_list)}")

exts = {}
for f in file_list:
    ext = f.suffix.lower()
    exts[ext] = exts.get(ext, 0) + 1
print(f"Extensions: {exts}")

# Print sample file paths
for f in file_list[:20]:
    rel = f.relative_to(base_dir)
    print(f"  {rel} ({f.stat().st_size:,} bytes)")
