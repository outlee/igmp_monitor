#!/usr/bin/env python3
"""Initialize SQLite database and insert 300 channel configurations."""
import asyncio
import ipaddress
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "probe"))

import aiosqlite

SQLITE_PATH = os.getenv("SQLITE_PATH", "/data/db/iptv.db")

GROUPS = [
    ("央视", 17),
    ("卫视", 34),
    ("地方", 50),
    ("付费", 30),
    ("体育", 20),
    ("影视", 40),
    ("少儿", 20),
    ("新闻", 20),
    ("综艺", 30),
    ("其他", 39),
]

CHANNEL_NAMES = {
    "央视": [
        "CCTV-1综合", "CCTV-2财经", "CCTV-3综艺", "CCTV-4中文国际", "CCTV-5体育",
        "CCTV-5+体育赛事", "CCTV-6电影", "CCTV-7国防军事", "CCTV-8电视剧", "CCTV-9纪录",
        "CCTV-10科教", "CCTV-11戏曲", "CCTV-12社会与法", "CCTV-13新闻", "CCTV-14少儿",
        "CCTV-15音乐", "CCTV-16奥林匹克",
    ],
    "卫视": [
        "湖南卫视", "浙江卫视", "江苏卫视", "东方卫视", "北京卫视",
        "深圳卫视", "广东卫视", "天津卫视", "安徽卫视", "山东卫视",
        "辽宁卫视", "黑龙江卫视", "云南卫视", "贵州卫视", "四川卫视",
        "湖北卫视", "河南卫视", "陕西卫视", "广西卫视", "海南卫视",
        "吉林卫视", "内蒙古卫视", "宁夏卫视", "青海卫视", "西藏卫视",
        "江西卫视", "重庆卫视", "福建卫视", "河北卫视", "山西卫视",
        "新疆卫视", "兵团卫视", "甘肃卫视", "龙虎网卫视",
    ],
    "地方": [f"地方频道{i+1:02d}" for i in range(50)],
    "付费": [f"付费电影{i+1:02d}" for i in range(30)],
    "体育": [f"体育赛事{i+1:02d}" for i in range(20)],
    "影视": [f"影视频道{i+1:02d}" for i in range(40)],
    "少儿": [f"少儿频道{i+1:02d}" for i in range(20)],
    "新闻": [f"新闻频道{i+1:02d}" for i in range(20)],
    "综艺": [f"综艺频道{i+1:02d}" for i in range(30)],
    "其他": [f"其他频道{i+1:02d}" for i in range(39)],
}

BASE_MCAST_IP = ipaddress.IPv4Address("239.1.1.1")
BASE_PORT = 1234


async def init_db():
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    db = await aiosqlite.connect(SQLITE_PATH)

    await db.executescript("""
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

    idx = 0
    for group_name, count in GROUPS:
        names = CHANNEL_NAMES.get(group_name, [f"{group_name}频道{i+1:02d}" for i in range(count)])
        for i in range(count):
            channel_id = f"ch{idx + 1:03d}"
            name = names[i] if i < len(names) else f"{group_name}{i + 1:02d}"
            mcast_ip = str(BASE_MCAST_IP + idx)
            port = BASE_PORT

            await db.execute(
                """INSERT OR IGNORE INTO channels
                   (id, name, multicast_ip, multicast_port, group_name, sort_order, enabled, expected_bitrate_kbps)
                   VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                (channel_id, name, mcast_ip, port, group_name, idx, 5000.0),
            )
            idx += 1

    await db.commit()
    await db.close()
    print(f"✅ Initialized {idx} channels in {SQLITE_PATH}")


if __name__ == "__main__":
    asyncio.run(init_db())
