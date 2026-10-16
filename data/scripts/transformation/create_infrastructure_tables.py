"""Create Dedicated Categorized Tables & Views for Critical Infrastructure in PostGIS.

Categories to separate / classify:
- hospitals (hospitals, clinics, tertiary and specialty healthcare)
- police (police stations, chowkis, DCP offices)
- fire_stations (fire stations and command centers)
- railway_stations (suburban railway stations and terminals)
- emergency_facilities (disaster control hubs, emergency administration, shelters)
"""

import os
import ssl
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()
RAW_URL = os.environ.get("DATABASE_URL", "")
CLEAN_URL = RAW_URL.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

INFRA_DDL = """
-- 1. Hospitals & Healthcare
CREATE TABLE IF NOT EXISTS hospitals AS
SELECT 
    infra_id, city_id, name, category as healthcare_type,
    ward, location, capacity, elevation_m, flood_vulnerable,
    data_source, attributes
FROM critical_infrastructure
WHERE category IN ('hospital', 'clinic', 'tertiary_healthcare', 'private_tertiary_healthcare', 'specialty_healthcare');

CREATE INDEX IF NOT EXISTS idx_hospitals_loc ON hospitals USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_hospitals_ward ON hospitals (ward);

-- 2. Police Stations
CREATE TABLE IF NOT EXISTS police AS
SELECT 
    infra_id, city_id, name, category,
    ward, location, capacity, elevation_m, flood_vulnerable,
    data_source, attributes
FROM critical_infrastructure
WHERE category = 'police';

CREATE INDEX IF NOT EXISTS idx_police_loc ON police USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_police_ward ON police (ward);

-- 3. Fire Stations
CREATE TABLE IF NOT EXISTS fire_stations AS
SELECT 
    infra_id, city_id, name, category,
    ward, location, capacity, elevation_m, flood_vulnerable,
    data_source, attributes
FROM critical_infrastructure
WHERE category = 'fire_station';

CREATE INDEX IF NOT EXISTS idx_fire_stations_loc ON fire_stations USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_fire_stations_ward ON fire_stations (ward);

-- 4. Railway Stations & Terminals
CREATE TABLE IF NOT EXISTS railway_stations AS
SELECT 
    infra_id, city_id, name, category,
    ward, location, capacity, elevation_m, flood_vulnerable,
    data_source, attributes
FROM critical_infrastructure
WHERE category IN ('railway_station', 'railway_terminal');

CREATE INDEX IF NOT EXISTS idx_railway_stations_loc ON railway_stations USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_railway_stations_ward ON railway_stations (ward);

-- 5. Emergency Facilities
CREATE TABLE IF NOT EXISTS emergency_facilities AS
SELECT 
    infra_id, city_id, name, category,
    ward, location, capacity, elevation_m, flood_vulnerable,
    data_source, attributes
FROM critical_infrastructure
WHERE category IN ('disaster_control_hub', 'emergency_administration', 'stormwater_pumping_station', 'airport_terminal');

CREATE INDEX IF NOT EXISTS idx_emergency_facilities_loc ON emergency_facilities USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_emergency_facilities_ward ON emergency_facilities (ward);
"""

async def create_infra_tables():
    print("=== CREATING DEDICATED CRITICAL INFRASTRUCTURE TABLES IN POSTGIS ===")
    conn = await asyncpg.connect(CLEAN_URL, ssl=SSL_CTX)
    
    # Drop existing if we need to recreate fresh
    await conn.execute("""
        DROP TABLE IF EXISTS hospitals CASCADE;
        DROP TABLE IF EXISTS police CASCADE;
        DROP TABLE IF EXISTS fire_stations CASCADE;
        DROP TABLE IF EXISTS railway_stations CASCADE;
        DROP TABLE IF EXISTS emergency_facilities CASCADE;
    """)
    print("Cleared existing views/tables.")
    
    await conn.execute(INFRA_DDL)
    print("Created dedicated tables and GIST spatial indexes.")
    
    # Verify counts
    counts = {
        "hospitals": await conn.fetchval("SELECT count(*) FROM hospitals"),
        "police": await conn.fetchval("SELECT count(*) FROM police"),
        "fire_stations": await conn.fetchval("SELECT count(*) FROM fire_stations"),
        "railway_stations": await conn.fetchval("SELECT count(*) FROM railway_stations"),
        "emergency_facilities": await conn.fetchval("SELECT count(*) FROM emergency_facilities")
    }
    
    print("\n=== DEDICATED INFRASTRUCTURE TABLES SUMMARY ===")
    for tbl, count in counts.items():
        print(f"  {tbl:<22}: {count:,} records")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(create_infra_tables())
