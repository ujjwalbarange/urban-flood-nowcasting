"""Stage 0: Aiven PostgreSQL/PostGIS Connectivity Diagnostic"""
import asyncio
import os
import ssl
import socket
import time
import json
from datetime import datetime, timezone
from pathlib import Path

# Load .env — find project root by walking up to urban-flood-nowcasting
from dotenv import load_dotenv
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR
for _ in range(10):
    if (_PROJECT_ROOT / ".env").exists():
        break
    _PROJECT_ROOT = _PROJECT_ROOT.parent
load_dotenv(_PROJECT_ROOT / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Parse connection components
def parse_url(url):
    """Extract host, port, db, user from DATABASE_URL."""
    clean = url.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]
    # postgresql://user:pass@host:port/dbname
    after_scheme = clean.split("://", 1)[1]
    userpass, rest = after_scheme.split("@", 1)
    user = userpass.split(":", 1)[0]
    hostport, dbname = rest.rsplit("/", 1)
    host, port = hostport.rsplit(":", 1)
    return {"user": user, "host": host, "port": int(port), "dbname": dbname, "clean_url": clean}

report = {
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "stage": "Stage 0: Database Connectivity Diagnostic",
    "checks": []
}

def log_check(name, status, detail=""):
    entry = {"check": name, "status": status, "detail": detail}
    report["checks"].append(entry)
    icon = "PASS" if status == "pass" else ("FAIL" if status == "fail" else "WARN")
    print(f"  [{icon}] {name}: {detail}")

print("=" * 70)
print("MUFNS Stage 0: Aiven PostgreSQL/PostGIS Connectivity Diagnostic")
print("=" * 70)

# 1. Check DATABASE_URL is set
print("\n--- Step 1: DATABASE_URL ---")
if not DATABASE_URL:
    log_check("DATABASE_URL present", "fail", "DATABASE_URL environment variable is empty")
    report["overall"] = "BLOCKED"
else:
    log_check("DATABASE_URL present", "pass", f"Found ({len(DATABASE_URL)} chars)")

try:
    parsed = parse_url(DATABASE_URL)
    log_check("URL parsing", "pass", f"host={parsed['host']}, port={parsed['port']}, db={parsed['dbname']}, user={parsed['user']}")
    report["connection"] = {
        "host": parsed["host"],
        "port": parsed["port"],
        "database": parsed["dbname"],
        "user": parsed["user"]
    }
except Exception as e:
    log_check("URL parsing", "fail", str(e))
    parsed = None

# 2. DNS resolution
print("\n--- Step 2: DNS Resolution ---")
if parsed:
    try:
        addrs = socket.getaddrinfo(parsed["host"], parsed["port"], socket.AF_UNSPEC, socket.SOCK_STREAM)
        ip_list = list(set(a[4][0] for a in addrs))
        log_check("DNS resolution", "pass", f"Resolved to {ip_list}")
        report["dns"] = {"resolved_ips": ip_list}
    except socket.gaierror as e:
        log_check("DNS resolution", "fail", f"Cannot resolve hostname: {e}")

# 3. TCP connectivity
print("\n--- Step 3: TCP Connectivity ---")
if parsed:
    try:
        sock = socket.create_connection((parsed["host"], parsed["port"]), timeout=10)
        log_check("TCP connection", "pass", f"Connected to {parsed['host']}:{parsed['port']}")
        sock.close()
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        log_check("TCP connection", "fail", f"{type(e).__name__}: {e}")
        report["tcp_error"] = str(e)

# 4. SSL handshake
print("\n--- Step 4: SSL Handshake ---")
if parsed:
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        sock = socket.create_connection((parsed["host"], parsed["port"]), timeout=10)
        ssl_sock = ctx.wrap_socket(sock, server_hostname=parsed["host"])
        log_check("SSL handshake", "pass", f"Protocol: {ssl_sock.version()}, Cipher: {ssl_sock.cipher()[0]}")
        ssl_sock.close()
    except Exception as e:
        log_check("SSL handshake", "fail", f"{type(e).__name__}: {e}")

# 5. asyncpg connection
print("\n--- Step 5: PostgreSQL Authentication ---")

async def test_asyncpg():
    if not parsed:
        return
    import asyncpg
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        t0 = time.time()
        conn = await asyncpg.connect(parsed["clean_url"], ssl=ctx, timeout=15)
        latency = round((time.time() - t0) * 1000, 1)
        log_check("asyncpg connect", "pass", f"Connected in {latency}ms")
        
        # PostgreSQL version
        pg_ver = await conn.fetchval("SELECT version()")
        log_check("PostgreSQL version", "pass", pg_ver.split(",")[0] if pg_ver else "unknown")
        
        # PostGIS
        try:
            postgis_ver = await conn.fetchval("SELECT PostGIS_Full_Version()")
            log_check("PostGIS version", "pass", postgis_ver[:80] if postgis_ver else "unknown")
        except Exception as e:
            log_check("PostGIS extension", "fail", str(e))
        
        # Database name
        db_name = await conn.fetchval("SELECT current_database()")
        log_check("Database name", "pass", db_name)
        
        # Table inventory
        rows = await conn.fetch("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema='public' AND table_type='BASE TABLE' 
            ORDER BY table_name
        """)
        log_check("Table count", "pass", f"{len(rows)} tables found")
        
        # Row counts for every table
        print("\n--- Step 6: Table Row Counts ---")
        table_inventory = []
        for r in rows:
            name = r['table_name']
            try:
                cnt = await conn.fetchval(f'SELECT count(*) FROM public."{name}"')
                table_inventory.append({"table": name, "rows": cnt})
                status = "pass" if cnt > 0 else "warn"
                log_check(f"  {name}", status, f"{cnt:,} rows")
            except Exception as e:
                table_inventory.append({"table": name, "rows": -1, "error": str(e)})
                log_check(f"  {name}", "fail", str(e)[:60])
        
        report["tables"] = table_inventory
        report["table_count"] = len(rows)
        
        # Spatial reference systems
        print("\n--- Step 7: Spatial Integrity ---")
        try:
            srid_count = await conn.fetchval("SELECT count(DISTINCT srid) FROM geometry_columns")
            log_check("Distinct SRIDs in use", "pass", f"{srid_count}")
            
            srid_rows = await conn.fetch("SELECT DISTINCT srid, count(*) as cnt FROM geometry_columns GROUP BY srid ORDER BY srid")
            for sr in srid_rows:
                log_check(f"  SRID {sr['srid']}", "pass", f"used in {sr['cnt']} geometry columns")
        except Exception as e:
            log_check("Spatial reference check", "fail", str(e)[:80])
        
        # Key dataset spot checks
        print("\n--- Step 8: Key Dataset Verification ---")
        
        # INSAT-3DR
        try:
            insat_count = await conn.fetchval("SELECT count(*) FROM satellite_rainfall_observations")
            hem_count = await conn.fetchval("SELECT count(*) FROM satellite_rainfall_observations WHERE product='HEM'")
            imc_count = await conn.fetchval("SELECT count(*) FROM satellite_rainfall_observations WHERE product='IMC'")
            log_check("INSAT-3DR total", "pass", f"{insat_count} granules (HEM={hem_count}, IMC={imc_count})")
        except Exception as e:
            log_check("INSAT-3DR", "fail", str(e)[:80])
        
        # GPM IMERG
        try:
            gpm_count = await conn.fetchval("SELECT count(*) FROM rainfall_satellite")
            log_check("GPM IMERG", "pass", f"{gpm_count} records")
        except Exception as e:
            log_check("GPM IMERG", "fail", str(e)[:80])
        
        # AWS rainfall
        try:
            aws_count = await conn.fetchval("SELECT count(*) FROM rainfall_observations")
            log_check("AWS rainfall gauges", "pass", f"{aws_count} records")
        except Exception as e:
            log_check("AWS rainfall", "fail", str(e)[:80])
        
        # Historical events
        try:
            hist_count = await conn.fetchval("SELECT count(*) FROM historical_flood_events")
            log_check("Historical flood events", "pass", f"{hist_count} records")
        except Exception as e:
            log_check("Historical floods", "fail", str(e)[:80])
        
        # Flood hotspots
        try:
            hs_count = await conn.fetchval("SELECT count(*) FROM flood_hotspots")
            log_check("Flood hotspots", "pass", f"{hs_count} records")
        except Exception as e:
            log_check("Flood hotspots", "fail", str(e)[:80])
        
        # Tide
        try:
            tide_count = await conn.fetchval("SELECT count(*) FROM tide_observations")
            log_check("Tide observations", "pass", f"{tide_count} records")
        except Exception as e:
            log_check("Tide observations", "fail", str(e)[:80])
        
        # DEM metadata
        try:
            dem_count = await conn.fetchval("SELECT count(*) FROM dem_metadata")
            log_check("DEM metadata", "pass", f"{dem_count} records")
        except Exception as e:
            log_check("DEM metadata", "fail", str(e)[:80])
        
        # LULC
        try:
            lulc_count = await conn.fetchval("SELECT count(*) FROM land_use_land_cover")
            log_check("LULC", "pass", f"{lulc_count} records")
        except Exception as e:
            log_check("LULC", "fail", str(e)[:80])
        
        # Imperviousness
        try:
            imp_count = await conn.fetchval("SELECT count(*) FROM impervious_surface_fractions")
            log_check("Impervious surface", "pass", f"{imp_count} records")
        except Exception as e:
            log_check("Impervious surface", "fail", str(e)[:80])
        
        # Soil
        for tbl in ["soil_types", "soil_hydro_groups", "soil_percolation_parameters"]:
            try:
                cnt = await conn.fetchval(f'SELECT count(*) FROM "{tbl}"')
                log_check(f"Soil: {tbl}", "pass", f"{cnt} records")
            except Exception as e:
                log_check(f"Soil: {tbl}", "fail", str(e)[:80])
        
        # Roads, buildings, population
        for tbl, label in [("mumbai_roads", "Roads"), ("buildings", "Buildings"), 
                           ("population_distribution_grids", "Population"), 
                           ("critical_infrastructure", "Infrastructure"),
                           ("mumbai_wards", "Wards")]:
            try:
                cnt = await conn.fetchval(f'SELECT count(*) FROM "{tbl}"')
                log_check(label, "pass", f"{cnt} records")
            except Exception as e:
                log_check(label, "fail", str(e)[:80])
        
        # Weather/NWP
        try:
            wf_count = await conn.fetchval("SELECT count(*) FROM weather_forecasts_grid")
            log_check("Weather forecasts", "pass", f"{wf_count} records")
        except Exception as e:
            log_check("Weather forecasts", "fail", str(e)[:80])
        
        # Data sources registry
        try:
            ds_count = await conn.fetchval("SELECT count(*) FROM data_sources")
            log_check("Data sources registry", "pass", f"{ds_count} records")
        except Exception as e:
            log_check("Data sources", "fail", str(e)[:80])
        
        await conn.close()
        report["overall"] = "CONNECTED"
        
    except Exception as e:
        log_check("asyncpg connect", "fail", f"{type(e).__name__}: {e}")
        report["overall"] = "CONNECTION_FAILED"
        report["connection_error"] = {
            "type": type(e).__name__,
            "message": str(e)
        }

asyncio.run(test_asyncpg())

# Summary
print("\n" + "=" * 70)
print(f"OVERALL STATUS: {report.get('overall', 'UNKNOWN')}")
print("=" * 70)

# Save JSON report
out_dir = _PROJECT_ROOT / "data" / "metadata"
out_dir.mkdir(parents=True, exist_ok=True)
json_path = out_dir / "stage0_db_diagnostic.json"
with open(json_path, "w") as f:
    json.dump(report, f, indent=2, default=str)
print(f"\nDiagnostic JSON saved: {json_path}")
