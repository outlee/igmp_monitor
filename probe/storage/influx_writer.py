import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from influxdb_client import Point, WritePrecision
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

from config import (
    INFLUXDB_BUCKET,
    INFLUXDB_ORG,
    INFLUXDB_TOKEN,
    INFLUXDB_URL,
    INFLUX_BATCH_SIZE,
    INFLUX_FLUSH_INTERVAL_MS,
)
from status_machine import ChannelMetrics, ChannelStatus

logger = logging.getLogger(__name__)


class InfluxBatchWriter:
    def __init__(self):
        self._client: InfluxDBClientAsync | None = None
        self._write_api = None
        self._buffer: List[Point] = []
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None

    async def start(self):
        self._client = InfluxDBClientAsync(
            url=INFLUXDB_URL,
            token=INFLUXDB_TOKEN,
            org=INFLUXDB_ORG,
        )
        self._write_api = self._client.write_api()
        self._flush_task = asyncio.create_task(self._flush_loop())

    async def stop(self):
        if self._flush_task:
            self._flush_task.cancel()
        await self._flush_now()
        if self._client:
            await self._client.close()

    async def write_metrics(self, metrics: ChannelMetrics, status: ChannelStatus):
        point = (
            Point("channel_metrics")
            .tag("channel_id", metrics.channel_id)
            .tag("channel_name", metrics.channel_name)
            .tag("status", status.value)
            .field("bitrate_kbps", float(metrics.bitrate_kbps))
            .field("cc_errors_per_sec", float(metrics.cc_errors_per_sec))
            .field("pcr_jitter_ms", float(metrics.pcr_jitter_ms))
            .field("video_brightness", float(metrics.video_brightness))
            .field("audio_rms", float(metrics.audio_rms))
            .field("is_black", int(metrics.is_black))
            .field("is_frozen", int(metrics.is_frozen))
            .field("is_silent", int(metrics.is_silent))
            .field("is_clipping", int(metrics.is_clipping))
            .field("is_mosaic", int(metrics.is_mosaic))
            .field("mosaic_ratio", float(metrics.mosaic_ratio))
            .field("is_stuttering", int(metrics.is_stuttering))
            .field("stutter_count", int(metrics.stutter_count))
            .time(datetime.now(timezone.utc), WritePrecision.SECONDS)
        )
        async with self._lock:
            self._buffer.append(point)
            if len(self._buffer) >= INFLUX_BATCH_SIZE:
                await self._flush_now_locked()

    async def _flush_loop(self):
        interval = INFLUX_FLUSH_INTERVAL_MS / 1000.0
        while True:
            await asyncio.sleep(interval)
            await self._flush_now()

    async def _flush_now(self):
        async with self._lock:
            await self._flush_now_locked()

    async def _flush_now_locked(self):
        if not self._buffer or self._write_api is None:
            return
        points = self._buffer[:]
        self._buffer.clear()
        try:
            await self._write_api.write(
                bucket=INFLUXDB_BUCKET,
                org=INFLUXDB_ORG,
                record=points,
            )
        except Exception as e:
            logger.warning("InfluxDB write error: %s", e)
