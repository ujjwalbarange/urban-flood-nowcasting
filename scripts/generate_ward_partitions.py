"""CLI script to generate and validate Mumbai ward partitions into subareas."""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))

from services.spatial.partitioning import generate_mumbai_subareas

def main():
    root = Path(__file__).resolve().parent.parent
    wards_path = root / "data" / "cities" / "mumbai" / "wards.geojson"
    
    print(f"Generating partitions from {wards_path}...")
    subareas_geojson, report = generate_mumbai_subareas(wards_path)

    # 1. Write to data/cities/mumbai/subareas.geojson
    out_path1 = root / "data" / "cities" / "mumbai" / "subareas.geojson"
    with open(out_path1, "w", encoding="utf-8") as f:
        json.dump(subareas_geojson, f, indent=2)
    print(f"Saved {len(subareas_geojson['features'])} subareas to {out_path1}")

    # 2. Write to mumbai_flood_data_package/01_city/subareas.geojson
    out_path2 = root / "mumbai_flood_data_package" / "01_city" / "subareas.geojson"
    out_path2.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path2, "w", encoding="utf-8") as f:
        json.dump(subareas_geojson, f, indent=2)
    print(f"Saved copy to {out_path2}")

    # 3. Write validation JSON report
    report_json_path = root / "data" / "metadata" / "ward_partition_validation.json"
    report_json_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Saved validation JSON to {report_json_path}")

    # 4. Write markdown report
    md_lines = [
        "# Mumbai Administrative Ward Partitioning & Subarea Validation Report",
        "",
        f"**Status:** {report['status']}  ",
        f"**Total Source Wards:** {report['total_source_wards']}  ",
        f"**Total Subareas Generated:** {report['total_subareas']}  ",
        f"**All Geometries Valid (OGC):** {report['all_geometries_valid']}  ",
        f"**Total Interior Overlaps:** {report['total_interior_overlaps']} km²  ",
        f"**Maximum Area Difference:** {report['max_area_diff_pct']:.6f}%  ",
        f"**Mean Area Difference:** {report['mean_area_diff_pct']:.6f}%  ",
        "",
        "## Ward Breakdown",
        "",
        "| Ward ID | Ward Name | Subarea Count | Subarea IDs | Registered Area (km²) | Subarea Sum (km²) | Area Diff (%) | Overlaps | Valid |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]
    for w in report["wards"]:
        md_lines.append(
            f"| `{w['ward_id']}` | {w['ward_name']} | {w['subarea_count']} | {', '.join(w['subarea_ids'])} | {w['original_area_km2']} | {w['subareas_total_area_km2']} | {w['area_difference_pct']:.6f}% | {w['interior_overlaps']} | {'PASS' if w['all_geometries_valid'] else 'FAIL'} |"
        )
    
    md_report_path = root / "data" / "metadata" / "WARD_PARTITION_VALIDATION_REPORT.md"
    with open(md_report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"Saved Markdown report to {md_report_path}")

if __name__ == "__main__":
    main()
