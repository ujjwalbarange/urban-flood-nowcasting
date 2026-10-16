import asyncio
import os
import ssl
import asyncpg
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get('DATABASE_URL').replace('postgresql+asyncpg://', 'postgresql://').split('?')[0]
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

async def run():
    conn = await asyncpg.connect(url, ssl=ctx)
    print("=== CRITICAL INFRASTRUCTURE CATEGORIES ===")
    cats = await conn.fetch("SELECT category, count(*) as cnt FROM critical_infrastructure GROUP BY category ORDER BY cnt DESC")
    for c in cats:
        print(f"  {c['category']}: {c['cnt']}")

    print("\n=== WATER BODIES TYPES ===")
    wtypes = await conn.fetch("SELECT feature_type, count(*) as cnt FROM water_bodies GROUP BY feature_type ORDER BY cnt DESC")
    for w in wtypes:
        print(f"  {w['feature_type']}: {w['cnt']}")

    print("\n=== SHELTERS ===")
    shelters = await conn.fetch("SELECT shelter_id, name, category, capacity_persons, status FROM shelters")
    for s in shelters:
        print(f"  {s['shelter_id']}: {s['name']} | category: {s['category']} | capacity: {s['capacity_persons']} | status: {s['status']}")

    await conn.close()

if __name__ == '__main__':
    asyncio.run(run())
