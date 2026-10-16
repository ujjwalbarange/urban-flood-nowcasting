import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()
raw_url = os.environ.get('DATABASE_URL')
url = raw_url.replace('postgresql+asyncpg://', 'postgresql://')

async def check():
    try:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        clean_url = url.split('?')[0]
        conn = await asyncpg.connect(clean_url, ssl=ctx)
        print('Connected successfully!')
        version = await conn.fetchval('SELECT version()')
        print('PostgreSQL version:', version[:50])
        postgis_ver = await conn.fetchval('SELECT PostGIS_Full_Version()')
        print('PostGIS version:', postgis_ver[:60])
        
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        print(f'\nTotal tables in public schema: {len(tables)}')
        for t in tables:
            tname = t['table_name']
            try:
                cnt = await conn.fetchval(f'SELECT count(*) FROM "{tname}"')
                print(f'  {tname}: {cnt} rows')
            except Exception as e:
                print(f'  {tname}: error {e}')
        await conn.close()
    except Exception as e:
        print(f'Database connection failed: {e}')

if __name__ == '__main__':
    asyncio.run(check())
