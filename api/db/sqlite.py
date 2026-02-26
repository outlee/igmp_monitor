import aiosqlite
from config import SQLITE_PATH

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        _db = await aiosqlite.connect(SQLITE_PATH)
        _db.row_factory = aiosqlite.Row
    return _db


async def close_db():
    global _db
    if _db:
        await _db.close()
        _db = None
