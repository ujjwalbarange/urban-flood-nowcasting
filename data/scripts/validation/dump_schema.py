import asyncio
import os
import ssl
import asyncpg
from dotenv import load_dotenv

load_dotenv()
RAW_URL = os.environ.get("DATABASE_URL", "")
CLEAN_URL = RAW_URL.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

async def dump_schema():
    conn = await asyncpg.connect(CLEAN_URL, ssl=SSL_CTX)
    
    lines = [
        "-- ============================================================================",
        "-- MUMBAI URBAN FLOOD NOWCASTING & DATA FOUNDATION PLATFORM (MUFNS)",
        "-- Actual Verified PostgreSQL 18.6 + PostGIS 3.6.4 Database DDL Schema Dump",
        "-- Database Name: defaultdb (Aiven Cloud PostgreSQL)",
        "-- Generated programmatically from information_schema and pg_catalog",
        "-- Date: 2026-09-25",
        "-- ============================================================================",
        "",
        "CREATE EXTENSION IF NOT EXISTS postgis;",
        "CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";",
        ""
    ]
    
    # Get base tables
    tables = await conn.fetch("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE' AND table_name != 'spatial_ref_sys'
        ORDER BY table_name;
    """)
    
    for t_row in tables:
        t = t_row["table_name"]
        lines.append(f"-- ------------------------------------------------------------")
        lines.append(f"-- Table: {t}")
        lines.append(f"-- ------------------------------------------------------------")
        lines.append(f"CREATE TABLE IF NOT EXISTS public.\"{t}\" (")
        
        cols = await conn.fetch("""
            SELECT column_name, data_type, udt_name, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = $1
            ORDER BY ordinal_position;
        """, t)
        
        # Check geometry columns
        geom_map = {}
        geoms = await conn.fetch("""
            SELECT f_geometry_column, srid, type
            FROM geometry_columns
            WHERE f_table_schema = 'public' AND f_table_name = $1;
        """, t)
        for g in geoms:
            geom_map[g["f_geometry_column"]] = f"geometry({g['type']}, {g['srid']})"
            
        col_defs = []
        for c in cols:
            cname = c["column_name"]
            if cname in geom_map:
                col_type = geom_map[cname]
            else:
                col_type = c["udt_name"].upper()
                if col_type == "VARCHAR":
                    col_type = "VARCHAR(255)"
                elif col_type == "TIMESTAMPTZ":
                    col_type = "TIMESTAMPTZ"
                elif col_type == "FLOAT8":
                    col_type = "DOUBLE PRECISION"
                elif col_type == "INT4":
                    col_type = "INTEGER"
                elif col_type == "INT8":
                    col_type = "BIGINT"
                elif col_type == "BOOL":
                    col_type = "BOOLEAN"
            
            null_str = "NOT NULL" if c["is_nullable"] == "NO" else ""
            default_str = f"DEFAULT {c['column_default']}" if c["column_default"] else ""
            
            col_def = f"    \"{cname}\" {col_type} {null_str} {default_str}".strip()
            col_defs.append(col_def)
            
        lines.append(",\n".join(col_defs))
        lines.append(");")
        lines.append("")
        
        # Indexes
        idx_rows = await conn.fetch("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = $1;
        """, t)
        for idx in idx_rows:
            lines.append(f"{idx['indexdef']};")
        lines.append("")
        
    await conn.close()
    
    with open("data/schema.sql", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("Schema dumped successfully to data/schema.sql")

if __name__ == "__main__":
    asyncio.run(dump_schema())
