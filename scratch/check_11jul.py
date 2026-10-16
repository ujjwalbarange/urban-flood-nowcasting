import re
from pathlib import Path
from collections import defaultdict

base_dir = Path("e:/urban/sih/urban-flood-nowcasting/MOSDAC_INSAT_DATA")
tif_files = list(base_dir.rglob("*11JUL2024*HEM*.tif"))

print(f"Total 11JUL2024 HEM files: {len(tif_files)}")
times = defaultdict(list)
for f in tif_files:
    m = re.search(r"_(\d{4})_L2B_HEM", f.name)
    if m:
        t = m.group(1)
        times[t].append(f)

for t, flist in sorted(times.items()):
    if len(flist) > 1:
        print(f"Time {t}: {len(flist)} files:")
        for f in flist:
            print(f"  {f.relative_to(base_dir)}")
    else:
        # single
        pass
print(f"Unique times on 11JUL2024: {len(times)}")
