import json
import logging
import time
from typing import Any, Dict

import redis.asyncio as aioredis

from config import REDIS_URL
from status_machine import ChannelMetrics, ChannelStatus

logger = logging.getLogger(__name__)

STATUS_TTL = 30


class RedisStateWriter:
    def __init__(self):
        self._redis: aioredis.Redis | None = None

    async def start(self):
        self._redis = aioredis.from_url(REDIS_URL, decode_responses=True)

    async def stop(self):
        if self._redis:
            await self._redis.aclose()

    async def update_channel_status(
        self,
        metrics: ChannelMetrics,
        status: ChannelStatus,
    ):
        if self._redis is None:
            return
        key = f"channel:{metrics.channel_id}:status"
        mapping: Dict[str, Any] = {
            "status": status.value,
            "channel_name": metrics.channel_name,
            "bitrate_kbps": metrics.bitrate_kbps,
            "is_black": int(metrics.is_black),
            "is_frozen": int(metrics.is_frozen),
            "is_silent": int(metrics.is_silent),
            "is_clipping": int(metrics.is_clipping),
            "cc_errors_per_sec": metrics.cc_errors_per_sec,
            "pcr_jitter_ms": metrics.pcr_jitter_ms,
            "audio_rms": metrics.audio_rms,
            "video_brightness": metrics.video_brightness,
            "thumbnail_path": metrics.thumbnail_path,
            "updated_at": time.time(),
        }
        try:
            pipe = self._redis.pipeline()
            pipe.hset(key, mapping=mapping)
            pipe.expire(key, STATUS_TTL)
            pipe.publish(
                "metrics_update",
                json.dumps(
                    {
                        "type": "channel_status",
                        "channel_id": metrics.channel_id,
                        "status": status.value,
                        "channel_name": metrics.channel_name,
                        "bitrate_kbps": metrics.bitrate_kbps,
                        "is_black": metrics.is_black,
                        "is_frozen": metrics.is_frozen,
                        "is_silent": metrics.is_silent,
                        "is_clipping": metrics.is_clipping,
                        "cc_errors_per_sec": metrics.cc_errors_per_sec,
                        "pcr_jitter_ms": metrics.pcr_jitter_ms,
                        "audio_rms": metrics.audio_rms,
                        "video_brightness": metrics.video_brightness,
                        "thumbnail_path": metrics.thumbnail_path,
                        "ts": time.time(),
                    }
                ),
            )
            await pipe.execute()
        except Exception as e:
            logger.warning("Redis write error: %s", e)

    async def publish_alert(self, alert_data: Dict):
        if self._redis is None:
            return
        try:
            await self._redis.publish("alert_update", json.dumps(alert_data))
        except Exception as e:
            logger.warning("Redis publish alert error: %s", e)

    async def get_all_channel_statuses(self) -> Dict[str, Dict]:
        if self._redis is None:
            return {}
        pattern = "channel:*:status"
        result = {}
        try:
            keys = await self._redis.keys(pattern)
            for key in keys:
                channel_id = key.split(":")[1]
                data = await self._redis.hgetall(key)
                result[channel_id] = data
        except Exception as e:
            logger.warning("Redis read error: %s", e)
        return result
