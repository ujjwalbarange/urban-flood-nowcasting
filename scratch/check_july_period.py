import asyncio
import os
import ssl
from collections import defaultdict
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
    rows = await conn.fetch("""
        SELECT observation_time, mean_value, max_value, mumbai_core_mean_value, mumbai_core_max_value
        FROM satellite_rainfall_observations
        WHERE product = 'HEM' AND year = 2024
          AND observation_time >= '2024-07-06 00:00:00+00'
          AND observation_time <= '2024-07-12 23:59:59+00'
        ORDER BY observation_time ASC;
    """)
    print(f"Total July 6-12 HEM records: {len(rows)}")
    if rows:
        print(f"Earliest: {rows[0]['observation_time']}")
        print(f"Latest:   {rows[-1]['observation_time']}")
        
        daily_mumbai_mean = defaultdict(float)
        daily_mumbai_max = defaultdict(float)
        daily_corridor_mean = defaultdict(float)
        daily_corridor_max = defaultdict(float)
        granules_per_day = defaultdict(int)

        for r in rows:
            dt = r['observation_time'].strftime('%Y-%m-%d')
            granules_per_day[dt] += 1
            daily_mumbai_mean[dt] += (r['mumbai_core_mean_value'] or 0.0) * 0.5
            daily_mumbai_max[dt] += (r['mumbai_core_max_value'] or 0.0) * 0.5
            daily_corridor_mean[dt] += (r['mean_value'] or 0.0) * 0.5
            daily_corridor_max[dt] += (r['max_value'] or 0.0) * 0.5

        print("\nDaily Accumulations:")
        for dt in sorted(daily_mumbai_mean.keys()):
            print(f"  {dt} ({granules_per_day[dt]:2d} granules): "
                  f"mumbai_mean={daily_mumbai_mean[dt]:6.2f} mm | "
                  f"mumbai_max={daily_mumbai_max[dt]:6.2f} mm | "
                  f"corridor_mean={daily_corridor_mean[dt]:6.2f} mm | "
                  f"corridor_max={daily_corridor_max[dt]:6.2f} mm")

    await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
