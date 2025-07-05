import asyncio
import asyncpg

async def test():
    try:
        # Пробуем разные варианты подключения
        urls = [
            "postgresql://tgm_user:tgm_secure_password_change_this@127.0.0.1:5432/tgm_db",
            "postgresql://tgm_user:tgm_secure_password_change_this@localhost:5432/tgm_db",
            "postgresql://tgm_user:tgm_secure_password_change_this@host.docker.internal:5432/tgm_db"
        ]
        
        for url in urls:
            print(f"Trying: {url}")
            try:
                conn = await asyncpg.connect(url)
                version = await conn.fetchval('SELECT version()')
                print(f"✅ SUCCESS! Connected to: {version}")
                await conn.close()
                return
            except Exception as e:
                print(f"❌ Failed: {e}")
                
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(test())