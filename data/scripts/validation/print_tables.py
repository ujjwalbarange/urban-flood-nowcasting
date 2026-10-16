import json

with open("data/scripts/validation/db_deep_audit_results.json", "r", encoding="utf-8") as f:
    db = json.load(f)

print(f"Database: {db['database_name']}")
print(f"Total Base Tables: {db['total_tables_count']}")
print(f"{'Table Name':<28} | {'Rows':>7} | {'Cols':>5} | {'Geom Column / Type':<30}")
print("-" * 78)
total_rows = 0
for t, info in sorted(db['tables'].items()):
    geom_str = "None"
    if info['geometries']:
        g = info['geometries'][0]
        geom_str = f"{g['column']} ({g['type']}, SRID {g['srid']})"
    print(f"{t:<28} | {info['row_count']:>7} | {info['columns_count']:>5} | {geom_str:<30}")
    total_rows += info['row_count']
print("-" * 78)
print(f"{'Total All Tables':<28} | {total_rows:>7}")
