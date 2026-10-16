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

async def main():
    conn = await asyncpg.connect(CLEAN_URL, ssl=SSL_CTX)
    tables = await conn.fetch("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'mufns_spatial_staging'
        ORDER BY table_name;
    """)
    for t in tables:
        tname = t["table_name"]
        cols = await conn.fetch(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'mufns_spatial_staging' AND table_name = '{tname}'
            ORDER BY ordinal_position;
        """)
        c_names = [c["column_name"] for c in cols]
        print(f"{tname}: {c_names}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
