import pathlib

SCRIPT = pathlib.Path("C:/Users/mfont/projects/HouseMktAnalyzr/validate_livability.py")

code = """import asyncio, asyncpg, json, os
from dotenv import load_dotenv

load_dotenv("C:/Users/mfont/projects/HouseMktAnalyzr/backend/.env")
DATABASE_URL = os.environ.get("DATABASE_URL")

async def main():
    conn = await asyncpg.connect(DATABASE_URL, ssl="prefer")
    print("Connected.")
    await conn.close()

asyncio.run(main())
"""

SCRIPT.write_text(code, encoding="utf-8")
print("done")