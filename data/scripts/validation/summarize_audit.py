import json

with open("data/scripts/validation/db_deep_audit_results.json", "r", encoding="utf-8") as f:
    db = json.load(f)

with open("data/scripts/validation/file_deep_audit_results.json", "r", encoding="utf-8") as f:
    files = json.load(f)

print("=== DATABASE OVERVIEW ===")
print("DB Name:", db["database_name"])
print("PostgreSQL Version:", db["postgres_version"][:60])
print("PostGIS Version:", db["postgis_version"][:60])
print("Total Base Tables:", db["total_tables_count"])
print()
print(f"{'Table Name':<28} | {'Rows':<7} | {'Cols':<5} | {'Geom Column / Type':<25}")
print("-" * 75)
for t, info in sorted(db["tables"].items()):
    geom_str = "None"
    if info["geometries"]:
        g = info["geometries"][0]
        geom_str = f"{g['column']} ({g['type']}, {g['srid']})"
    print(f"{t:<28} | {info['row_count']:<7} | {info['columns_count']:<5} | {geom_str:<25}")

print("\n=== SPECIFIC DATABASE AUDIT CHECKS ===")
for k, v in db.items():
    if k.endswith("_audit"):
        print(f"--- {k} ---")
        for sub_k, sub_v in v.items():
            if isinstance(sub_v, list) and len(sub_v) > 10:
                print(f"  {sub_k}: list of {len(sub_v)} items -> sample: {sub_v[:3]}")
            else:
                print(f"  {sub_k}: {sub_v}")

print("\n=== FILE SYSTEM AUDIT CHECKS ===")
print("1. DEM GLO-30:")
print(json.dumps(files.get("dem_cop30"), indent=2))
print("2. Terrain Derivatives:")
for name, dinfo in files.get("derivatives", {}).items():
    print(f"  {name:<18}: shape={dinfo['shape']}, min={dinfo['min']:.2f}, max={dinfo['max']:.2f}, mean={dinfo['mean']:.2f}, size={dinfo['size_bytes']:,} B")
print("3. GeoJSON Feature Counts:")
for name, ginfo in files.get("geojsons", {}).items():
    print(f"  {name:<24}: {ginfo['feature_count']:5} features, types={ginfo['geom_types']}, path={ginfo['path']}")
print("4. CSV Records Count:")
for name, cinfo in files.get("csvs", {}).items():
    print(f"  {name:<24}: {cinfo['row_count']:6} rows, cols={len(cinfo['columns'])}, path={cinfo['path']}")
