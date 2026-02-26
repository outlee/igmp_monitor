import logging
from typing import List

from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

from config import INFLUXDB_BUCKET, INFLUXDB_ORG, INFLUXDB_TOKEN, INFLUXDB_URL
from models.channel import MetricPoint

logger = logging.getLogger(__name__)

_client: InfluxDBClientAsync | None = None


async def get_influx() -> InfluxDBClientAsync:
    global _client
    if _client is None:
        _client = InfluxDBClientAsync(
            url=INFLUXDB_URL,
            token=INFLUXDB_TOKEN,
            org=INFLUXDB_ORG,
        )
    return _client


async def close_influx():
    global _client
    if _client:
        await _client.close()
        _client = None


async def query_channel_metrics(channel_id: str, range_str: str = "5m") -> List[MetricPoint]:
    try:
        client = await get_influx()
        query_api = client.query_api()
        flux = f"""
from(bucket: "{INFLUXDB_BUCKET}")
  |> range(start: -{range_str})
  |> filter(fn: (r) => r._measurement == "channel_metrics")
  |> filter(fn: (r) => r.channel_id == "{channel_id}")
  |> filter(fn: (r) => r._field =~ /bitrate_kbps|cc_errors_per_sec|pcr_jitter_ms|video_brightness|audio_rms|is_black|is_frozen|is_silent|status/)
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
"""
        tables = await query_api.query(flux)
        points = []
        for table in tables:
            for record in table.records:
                values = record.values
                points.append(
                    MetricPoint(
                        time=str(record.get_time()),
                        bitrate_kbps=float(values.get("bitrate_kbps", 0) or 0),
                        cc_errors_per_sec=float(values.get("cc_errors_per_sec", 0) or 0),
                        pcr_jitter_ms=float(values.get("pcr_jitter_ms", 0) or 0),
                        video_brightness=float(values.get("video_brightness", 0) or 0),
                        audio_rms=float(values.get("audio_rms", 0) or 0),
                        is_black=int(values.get("is_black", 0) or 0),
                        is_frozen=int(values.get("is_frozen", 0) or 0),
                        is_silent=int(values.get("is_silent", 0) or 0),
                        status=str(values.get("status", "NORMAL") or "NORMAL"),
                    )
                )
        return points
    except Exception as e:
        logger.warning("InfluxDB query error: %s", e)
        return []
