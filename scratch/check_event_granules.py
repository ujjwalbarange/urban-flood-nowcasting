import asyncio
import os
import ssl
from datetime import datetime, timezone
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

    events_to_check = [
        ("July 7-11 2024", datetime(2024, 7, 7, 0, 0, tzinfo=timezone.utc), datetime(2024, 7, 11, 23, 59, 59, tzinfo=timezone.utc)),
        ("July 23-26 2024", datetime(2024, 7, 23, 0, 0, tzinfo=timezone.utc), datetime(2024, 7, 26, 23, 59, 59, tzinfo=timezone.utc)),
        ("August 13-21 2025", datetime(2025, 8, 13, 0, 0, tzinfo=timezone.utc), datetime(2025, 8, 21, 23, 59, 59, tzinfo=timezone.utc)),
    ]

    print("Checking available granules for all historical events in database:")
    for name, start_t, end_t in events_to_check:
        hem_cnt = await conn.fetchval("""
            SELECT count(*) FROM public.satellite_rainfall_observations
            WHERE product = 'HEM' AND observation_time >= $1 AND observation_time <= $2;
        """, start_t, end_t)
        imc_cnt = await conn.fetchval("""
            SELECT count(*) FROM public.satellite_rainfall_observations
            WHERE product = 'IMC' AND observation_time >= $1 AND observation_time <= $2;
        """, start_t, end_t)
        gpm_cnt = await conn.fetchval("""
            SELECT count(*) FROM public.rainfall_satellite
            WHERE timestamp >= $1 AND timestamp <= $2;
        """, start_t, end_t)

        print(f"\n{name} ({start_t} to {end_t}):")
        print(f"  HEM granules: {hem_cnt}")
        print(f"  IMC granules: {imc_cnt}")
        print(f"  GPM records:  {gpm_cnt}")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
