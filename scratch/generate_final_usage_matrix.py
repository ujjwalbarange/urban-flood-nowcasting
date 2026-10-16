"""Stage 1 / Step 7: Final Comprehensive Dataset Usage Matrix Generator.

Queries public.dataset_registry and public.information_schema to evaluate all datasets
and assign their exact operational status, pipeline stage, and justification.
"""

import asyncio
import json
import os
import ssl
from pathlib import Path
import asyncpg
from dotenv import load_dotenv

project_root = Path(__file__).resolve().parent.parent
load_dotenv(project_root / ".env")

RAW_URL = os.environ.get("DATABASE_URL", "")
CLEAN_URL = RAW_URL.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE


async def main():
    conn = await asyncpg.connect(CLEAN_URL, ssl=SSL_CTX)

    rows = await conn.fetch("""
        SELECT dataset_id, dataset_name, category, source_provider, spatial_resolution,
               temporal_coverage, pipeline_stage, input_output_role, status, db_table,
               record_count, provenance_notes
        FROM public.dataset_registry
        ORDER BY pipeline_stage, dataset_id;
    """)

    print(f"Total datasets in registry: {len(rows)}")

    # Also query total tables in public schema
    tables = await conn.fetch("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        ORDER BY table_name;
    """)
    print(f"Total public tables in database: {len(tables)}")

    matrix_rows = []
    for r in rows:
        t_name = r["db_table"]
        actual_cnt = 0
        if t_name:
            try:
                actual_cnt = await conn.fetchval(f"SELECT count(*) FROM public.{t_name};")
            except Exception:
                actual_cnt = r["record_count"] or 0
        else:
            actual_cnt = r["record_count"] or 0

        matrix_rows.append({
            "dataset_id": r["dataset_id"],
            "dataset_name": r["dataset_name"],
            "category": r["category"],
            "source": r["source_provider"],
            "spatial_resolution": r["spatial_resolution"],
            "temporal_coverage": r["temporal_coverage"],
            "pipeline_stage": r["pipeline_stage"],
            "role": r["input_output_role"],
            "status": r["status"],
            "db_table": t_name or "N/A",
            "records": actual_cnt,
            "provenance": r["provenance_notes"],
        })

    await conn.close()

    # Save to json
    out_json = project_root / "data" / "metadata" / "dataset_usage_matrix.json"
    with open(out_json, "w") as f:
        json.dump(matrix_rows, f, indent=2)
    print(f"Dataset matrix saved: {out_json}")


if __name__ == "__main__":
    asyncio.run(main())
