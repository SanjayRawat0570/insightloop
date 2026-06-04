import asyncio
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect(user='user', password='pass', database='insightloop', host='127.0.0.1', port=5432)
        rows = await conn.fetch('SELECT 1 as v')
        print('connected', rows)
        await conn.close()
    except Exception as e:
        print('error', type(e).__name__, e)

if __name__ == '__main__':
    asyncio.run(main())
