import logging
import time
from dataclasses import dataclass
from typing import List, Optional

import aiosqlite

from config import SQLITE_PATH

logger = logging.getLogger(__name__)


@dataclass
class ChannelConfig:
    id: str
    name: str
    multicast_ip: str
    multicast_port: int
    group_name: str
    sort_order: int
    enabled: bool
    sim_video: Optional[str]
    expected_bitrate_kbps: float = 0.0


class SQLiteDB:
    def __init__(self, db_path: str = SQLITE_PATH):
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    async def start(self):
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._create_tables()

    async def stop(self):
        if self._db:
            await self._db.close()

    async def _create_tables(self):
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS channels (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                multicast_ip TEXT NOT NULL,
                multicast_port INTEGER DEFAULT 1234,
                group_name TEXT DEFAULT 'default',
                sort_order INTEGER DEFAULT 0,
                enabled BOOLEAN DEFAULT 1,
                sim_video TEXT,
                expected_bitrate_kbps REAL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT NOT NULL,
                channel_name TEXT,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT DEFAULT 'ACTIVE',
                message TEXT,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                resolved_at DATETIME,
                ack_at DATETIME,
                thumbnail_path TEXT,
                FOREIGN KEY (channel_id) REFERENCES channels(id)
            );

            CREATE TABLE IF NOT EXISTS alert_suppression (
                channel_id TEXT NOT NULL,
                alert_type TEXT NOT NULL,
                suppressed_until REAL NOT NULL,
                PRIMARY KEY (channel_id, alert_type)
            );

            CREATE INDEX IF NOT EXISTS idx_alerts_channel ON alerts(channel_id, started_at DESC);
            CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status, started_at DESC);
        """)
        await self._db.commit()

    async def get_enabled_channels(self) -> List[ChannelConfig]:
        async with self._db.execute(
            "SELECT * FROM channels WHERE enabled=1 ORDER BY sort_order ASC"
        ) as cur:
            rows = await cur.fetchall()
        return [
            ChannelConfig(
                id=row["id"],
                name=row["name"],
                multicast_ip=row["multicast_ip"],
                multicast_port=row["multicast_port"],
                group_name=row["group_name"],
                sort_order=row["sort_order"],
                enabled=bool(row["enabled"]),
                sim_video=row["sim_video"],
                expected_bitrate_kbps=float(row["expected_bitrate_kbps"] or 0),
            )
            for row in rows
        ]

    async def upsert_alert(
        self,
        channel_id: str,
        channel_name: str,
        alert_type: str,
        severity: str,
        message: str,
        thumbnail_path: str = "",
    ) -> int:
        async with self._db.execute(
            """SELECT id FROM alerts
               WHERE channel_id=? AND alert_type=? AND status='ACTIVE'
               ORDER BY started_at DESC LIMIT 1""",
            (channel_id, alert_type),
        ) as cur:
            existing = await cur.fetchone()
        if existing:
            return existing["id"]
        async with self._db.execute(
            """INSERT INTO alerts (channel_id, channel_name, alert_type, severity, message, thumbnail_path)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (channel_id, channel_name, alert_type, severity, message, thumbnail_path),
        ) as cur:
            row_id = cur.lastrowid
        await self._db.commit()
        return row_id

    async def resolve_alert(self, channel_id: str, alert_type: str):
        await self._db.execute(
            """UPDATE alerts SET status='RESOLVED', resolved_at=CURRENT_TIMESTAMP
               WHERE channel_id=? AND alert_type=? AND status='ACTIVE'""",
            (channel_id, alert_type),
        )
        await self._db.commit()

    async def update_channel_name(self, channel_id: str, name: str):
        await self._db.execute(
            "UPDATE channels SET name=? WHERE id=?",
            (name, channel_id),
        )
        await self._db.commit()
