import asyncio
import json
import logging
import time
from typing import Set

import redis.asyncio as aioredis
from fastapi import WebSocket

from config import REDIS_URL
from db.redis_client import get_redis

logger = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._subscriber_task: asyncio.Task | None = None

    async def start(self):
        self._subscriber_task = asyncio.create_task(self._redis_subscriber())

    async def stop(self):
        if self._subscriber_task:
            self._subscriber_task.cancel()
            try:
                await self._subscriber_task
            except asyncio.CancelledError:
                pass

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info("WebSocket connected, total: %d", len(self.active_connections))
        await self._send_batch_update(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info("WebSocket disconnected, total: %d", len(self.active_connections))

    async def broadcast(self, message: str):
        dead = set()
        for ws in list(self.active_connections):
            try:
                await ws.send_text(message)
            except Exception:
                dead.add(ws)
        self.active_connections -= dead

    async def _send_batch_update(self, websocket: WebSocket):
        try:
            redis = await get_redis()
            keys = await redis.keys("channel:*:status")
            channels = []
            for key in keys:
                channel_id = key.split(":")[1]
                data = await redis.hgetall(key)
                if data:
                    channels.append({
                        "channel_id": channel_id,
                        "channel_name": data.get("channel_name", channel_id),
                        "status": data.get("status", "OFFLINE"),
                        "bitrate_kbps": float(data.get("bitrate_kbps", 0)),
                        "is_black": bool(int(data.get("is_black", 0))),
                        "is_frozen": bool(int(data.get("is_frozen", 0))),
                        "is_silent": bool(int(data.get("is_silent", 0))),
                        "is_clipping": bool(int(data.get("is_clipping", 0))),
                        "cc_errors_per_sec": float(data.get("cc_errors_per_sec", 0)),
                        "pcr_jitter_ms": float(data.get("pcr_jitter_ms", 0)),
                        "audio_rms": float(data.get("audio_rms", 0)),
                        "video_brightness": float(data.get("video_brightness", 0)),
                        "thumbnail_path": data.get("thumbnail_path", ""),
                        "updated_at": float(data.get("updated_at", 0)),
                    })
            msg = json.dumps({"type": "batch_update", "channels": channels, "ts": time.time()})
            await websocket.send_text(msg)
        except Exception as e:
            logger.warning("Batch update error: %s", e)

    async def _redis_subscriber(self):
        while True:
            try:
                r = aioredis.from_url(REDIS_URL, decode_responses=True)
                async with r.pubsub() as pubsub:
                    await pubsub.subscribe("metrics_update", "alert_update")
                    logger.info("Redis pub/sub subscribed")
                    async for message in pubsub.listen():
                        if message["type"] == "message":
                            await self.broadcast(message["data"])
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Redis subscriber error: %s, retrying in 3s", e)
                await asyncio.sleep(3)


ws_manager = WebSocketManager()
