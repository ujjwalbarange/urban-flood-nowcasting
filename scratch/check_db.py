import asyncio, sys, os
sys.path.insert(0, os.path.abspath('.'))
from services.database.connection import engine, verify_db_connectivity
from sqlalchemy import text

async def main():
    ok = await verify_db_connectivity()
    print("Database Online:", ok)
    if not ok:
        return
    
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"))
        tables = [r[0] for r in res.fetchall()]
        print(f"Total tables: {len(tables)}")
        for t in tables:
            try:
                cnt = (await conn.execute(text(f'SELECT count(*) FROM "{t}"'))).scalar()
                print(f"  {t}: {cnt} rows")
            except Exception as e:
                print(f"  {t}: error counting ({e})")

if __name__ == "__main__":
    asyncio.run(main())
