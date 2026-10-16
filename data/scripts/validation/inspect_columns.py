import asyncio, os, ssl, asyncpg
from dotenv import load_dotenv

load_dotenv()
url = os.environ.get('DATABASE_URL').replace('postgresql+asyncpg://', 'postgresql://').split('?')[0]
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

async def run():
    conn = await asyncpg.connect(url, ssl=ctx)
    tables = ['cities', 'wards', 'historical_flood_events', 'critical_infrastructure', 'drainage_nodes', 'drainage_links', 'pumping_stations', 'road_segments', 'shelters']
    for t in tables:
        cols = await conn.fetch('''
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = $1
            ORDER BY ordinal_position;
        ''', t)
        print(f'=== {t} ===')
        for c in cols:
            print(f'  {c["column_name"]}: {c["data_type"]}')
    await conn.close()

if __name__ == '__main__':
    asyncio.run(run())
