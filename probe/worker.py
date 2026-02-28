import asyncio
import io
import logging
import socket
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

import av
import numpy as np

from analyzers.audio_analyzer import AudioAnalyzer
from analyzers.bitrate import BitrateCalculator
from analyzers.video_analyzer import VideoAnalyzer
from config import (
    CHANNELS_PER_WORKER,
    FRAME_SAMPLE_INTERVAL_SEC,
    UDP_TIMEOUT_SEC,
)
from status_machine import AlertType, ChannelMetrics, ChannelStatus, evaluate_status, get_active_alerts
from storage.influx_writer import InfluxBatchWriter
from storage.redis_writer import RedisStateWriter
from storage.sqlite_db import ChannelConfig, SQLiteDB
from ts_parser import TSParser

logger = logging.getLogger(__name__)


class ChannelMonitor:
    def __init__(
        self,
        config: ChannelConfig,
        redis_writer: RedisStateWriter,
        influx_writer: InfluxBatchWriter,
        sqlite_db: SQLiteDB,
        executor: ThreadPoolExecutor,
    ):
        self.config = config
        self.redis_writer = redis_writer
        self.influx_writer = influx_writer
        self.sqlite_db = sqlite_db
        self.executor = executor
        self.ts_parser = TSParser(config.id)
        self.bitrate_calc = BitrateCalculator(window_sec=5.0)
        self.video_analyzer = VideoAnalyzer(config.id)
        self.audio_analyzer = AudioAnalyzer()
        self._last_frame_time = 0.0
        self._cc_window_start = time.monotonic()
        self._cc_window_count = 0
        self._prev_status: Optional[ChannelStatus] = None
        self._published_alerts: Dict[str, int] = {}  # "channel_id:alert_type" -> alert_id
        self._frame_buffer: List[bytes] = []
        self._audio_buffer: List[np.ndarray] = []
        self._av_container: Optional[av.container.InputContainer] = None
        self._ts_fifo = io.BytesIO()
        self._ts_fifo_size = 0
        self._last_audio_pts: Optional[float] = None

    def _create_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)
        sock.bind(("", self.config.multicast_port))
        mreq = struct.pack("4sL", socket.inet_aton(self.config.multicast_ip), socket.INADDR_ANY)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        sock.setblocking(False)
        return sock

    async def _recv_udp(self, sock: socket.socket) -> Optional[bytes]:
        loop = asyncio.get_event_loop()
        try:
            data = await asyncio.wait_for(
                loop.run_in_executor(None, sock.recv, 65536),
                timeout=UDP_TIMEOUT_SEC,
            )
            return data
        except asyncio.TimeoutError:
            return None
        except Exception:
            return None

    async def _analyze_video_frame(self, frame_bgr: np.ndarray, ts: float, corrupt_ratio: float = 0.0) -> Dict:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.video_analyzer.analyze_frame,
            frame_bgr,
            ts,
            corrupt_ratio,
        )

    def _decode_av_frame(self, ts_data: bytes) -> Optional[Tuple[np.ndarray, float]]:
        try:
            buf = io.BytesIO(ts_data)
            container = av.open(buf, format="mpegts", options={"analyzeduration": "500000"})
            total = 0
            corrupt = 0
            result_img = None
            for stream in container.streams.video:
                stream.thread_type = "NONE"
                for frame in container.decode(stream):
                    total += 1
                    # 尝试访问 frame.corrupt（部分 PyAV 版本有此属性）
                    try:
                        if frame.corrupt:
                            corrupt += 1
                    except AttributeError:
                        pass
                    if result_img is None:
                        result_img = frame.to_ndarray(format="bgr24")
            container.close()
            corrupt_ratio = (corrupt / total) if total > 0 else 0.0
            if result_img is not None:
                return result_img, corrupt_ratio
        except Exception:
            pass
        return None

    def _decode_audio_pts(self, ts_data: bytes) -> Optional[Tuple[np.ndarray, int, float, int]]:
        """解码音频帧并返回 (samples_int16, sample_rate, pts_sec, samples_count)"""
        try:
            buf = io.BytesIO(ts_data)
            container = av.open(buf, format="mpegts", options={"analyzeduration": "500000"})
            for stream in container.streams.audio:
                for frame in container.decode(stream):
                    samples = frame.to_ndarray()  # shape: (channels, samples)
                    if samples.ndim > 1:
                        samples = samples.mean(axis=0)  # 混合为单声道
                    samples_i16 = (samples * 32767).clip(-32768, 32767).astype(np.int16)
                    sr = frame.sample_rate
                    pts_sec = float(frame.pts * stream.time_base) if frame.pts is not None else 0.0
                    samples_count = samples.shape[-1]
                    container.close()
                    return samples_i16, sr, pts_sec, samples_count
            container.close()
        except Exception:
            pass
        return None

    async def run(self):
        sock = None
        try:
            sock = self._create_socket()
        except OSError as e:
            logger.warning("Cannot bind socket for %s: %s", self.config.id, e)

        frame_result = {
            "is_black": False,
            "is_frozen": False,
            "brightness": 100.0,
            "thumbnail_path": "",
        }
        audio_result = {
            "rms": 0.1,
            "is_silent": False,
            "is_clipping": False,
            "clip_ratio": 0.0,
        }
        ts_buffer = bytearray()
        last_metrics_time = time.monotonic()
        cc_count_in_window = 0
        window_start = time.monotonic()

        while True:
            now = time.monotonic()
            now_wall = time.time()

            if sock is None:
                await asyncio.sleep(5)
                try:
                    sock = self._create_socket()
                except OSError:
                    pass
                continue

            data = await self._recv_udp(sock)
            if data is None:
                metrics = ChannelMetrics(
                    channel_id=self.config.id,
                    channel_name=self.ts_parser.service_name or self.config.name,
                    is_offline=True,
                    timestamp=now_wall,
                )
                status = ChannelStatus.OFFLINE
                await self._handle_status_change(metrics, status)
                await asyncio.sleep(1.0)
                continue

            self.ts_parser.feed(data)
            self.bitrate_calc.update(len(data), now)

            ts_buffer.extend(data)

            if now - self._last_frame_time >= FRAME_SAMPLE_INTERVAL_SEC:
                if len(ts_buffer) >= 1316:
                    chunk = bytes(ts_buffer[:65536])
                    ts_buffer.clear()
                    loop = asyncio.get_event_loop()
                    decode_result = await loop.run_in_executor(
                        self.executor, self._decode_av_frame, chunk
                    )
                    if decode_result is not None:
                        decoded_img, corrupt_ratio = decode_result
                        frame_result = await self._analyze_video_frame(decoded_img, now_wall, corrupt_ratio)

                    # 同时解码音频进行卡顿检测
                    audio_decode_result = await loop.run_in_executor(
                        self.executor, self._decode_audio_pts, chunk
                    )
                    if audio_decode_result is not None:
                        a_samples, a_sr, a_pts, a_count = audio_decode_result
                        audio_result = await loop.run_in_executor(
                            self.executor,
                            lambda: self.audio_analyzer.analyze_chunk(
                                a_samples, a_sr, now_wall,
                                pts=a_pts, samples_count=a_count
                            )
                        )
                self._last_frame_time = now

            if now - last_metrics_time >= 1.0:
                elapsed = now - window_start
                cc_per_sec = cc_count_in_window / elapsed if elapsed > 0 else 0.0
                cc_count_in_window = self.ts_parser.cc_errors
                self.ts_parser.reset_cc_errors()
                window_start = now

                channel_name = self.ts_parser.service_name or self.config.name
                metrics = ChannelMetrics(
                    channel_id=self.config.id,
                    channel_name=channel_name,
                    is_offline=False,
                    is_black=frame_result["is_black"],
                    is_frozen=frame_result["is_frozen"],
                    is_silent=audio_result["is_silent"],
                    is_clipping=audio_result["is_clipping"],
                    is_mosaic=frame_result.get("is_mosaic", False),
                    mosaic_ratio=frame_result.get("mosaic_ratio", 0.0),
                    is_stuttering=audio_result.get("is_stuttering", False),
                    stutter_count=audio_result.get("stutter_count", 0),
                    cc_errors_per_sec=cc_per_sec,
                    pcr_jitter_ms=self.ts_parser.pcr_jitter_ms,
                    bitrate_kbps=self.bitrate_calc.bitrate_kbps,
                    expected_bitrate_kbps=self.config.expected_bitrate_kbps,
                    audio_rms=audio_result["rms"],
                    video_brightness=frame_result["brightness"],
                    thumbnail_path=frame_result.get("thumbnail_path", ""),
                    timestamp=now_wall,
                )

                if channel_name != self.config.name and channel_name:
                    asyncio.create_task(
                        self.sqlite_db.update_channel_name(self.config.id, channel_name)
                    )

                status = evaluate_status(metrics)
                await self._handle_status_change(metrics, status)
                last_metrics_time = now

    async def _handle_status_change(self, metrics: ChannelMetrics, status: ChannelStatus):
        await self.redis_writer.update_channel_status(metrics, status)

        try:
            await self.influx_writer.write_metrics(metrics, status)
        except Exception as e:
            logger.debug("Influx write skipped: %s", e)

        alerts = get_active_alerts(metrics)
        severity_map = {
            AlertType.BLACK_SCREEN: "CRITICAL",
            AlertType.FROZEN: "CRITICAL",
            AlertType.SILENT: "CRITICAL",
            AlertType.OFFLINE: "CRITICAL",
            AlertType.CLIPPING: "WARNING",
            AlertType.CC_ERROR: "WARNING",
            AlertType.PCR_JITTER: "WARNING",
            AlertType.BITRATE_ABNORMAL: "WARNING",
            AlertType.MOSAIC: "WARNING",
            AlertType.AUDIO_STUTTER: "WARNING",
        }

        for alert_type in alerts:
            key = f"{metrics.channel_id}:{alert_type.value}"
            try:
                alert_id = await self.sqlite_db.upsert_alert(
                    channel_id=metrics.channel_id,
                    channel_name=metrics.channel_name,
                    alert_type=alert_type.value,
                    severity=severity_map.get(alert_type, "WARNING"),
                    message=f"{metrics.channel_name}: {alert_type.value}",
                    thumbnail_path=metrics.thumbnail_path,
                )
                if self._published_alerts.get(key) != alert_id:
                    self._published_alerts[key] = alert_id
                    await self.redis_writer.publish_alert(
                        {
                            "type": "alert_new",
                            "alert_id": alert_id,
                            "channel_id": metrics.channel_id,
                            "channel_name": metrics.channel_name,
                            "alert_type": alert_type.value,
                            "severity": severity_map.get(alert_type, "WARNING"),
                            "status": status.value,
                            "ts": metrics.timestamp,
                        }
                    )
            except Exception as e:
                logger.debug("Alert upsert error: %s", e)

        # 解除已恢复的 CRITICAL 告警
        if not metrics.is_offline:
            key = f"{metrics.channel_id}:{AlertType.OFFLINE.value}"
            self._published_alerts.pop(key, None)
            try:
                await self.sqlite_db.resolve_alert(metrics.channel_id, AlertType.OFFLINE.value)
            except Exception:
                pass

        if not metrics.is_black:
            key = f"{metrics.channel_id}:{AlertType.BLACK_SCREEN.value}"
            self._published_alerts.pop(key, None)
            try:
                await self.sqlite_db.resolve_alert(metrics.channel_id, AlertType.BLACK_SCREEN.value)
            except Exception:
                pass

        if not metrics.is_frozen:
            key = f"{metrics.channel_id}:{AlertType.FROZEN.value}"
            self._published_alerts.pop(key, None)
            try:
                await self.sqlite_db.resolve_alert(metrics.channel_id, AlertType.FROZEN.value)
            except Exception:
                pass

        if not metrics.is_silent:
            key = f"{metrics.channel_id}:{AlertType.SILENT.value}"
            self._published_alerts.pop(key, None)
            try:
                await self.sqlite_db.resolve_alert(metrics.channel_id, AlertType.SILENT.value)
            except Exception:
                pass

        # 解除已恢复的 WARNING 告警
        if not metrics.is_mosaic:
            key = f"{metrics.channel_id}:{AlertType.MOSAIC.value}"
            self._published_alerts.pop(key, None)
            try:
                await self.sqlite_db.resolve_alert(metrics.channel_id, AlertType.MOSAIC.value)
            except Exception:
                pass

        if not metrics.is_stuttering:
            key = f"{metrics.channel_id}:{AlertType.AUDIO_STUTTER.value}"
            self._published_alerts.pop(key, None)
            try:
                await self.sqlite_db.resolve_alert(metrics.channel_id, AlertType.AUDIO_STUTTER.value)
            except Exception:
                pass

        if not metrics.is_clipping:
            key = f"{metrics.channel_id}:{AlertType.CLIPPING.value}"
            self._published_alerts.pop(key, None)
            try:
                await self.sqlite_db.resolve_alert(metrics.channel_id, AlertType.CLIPPING.value)
            except Exception:
                pass

        self._prev_status = status


class ChannelWorker:
    def __init__(self, worker_id: int, channels: List[ChannelConfig]):
        self.worker_id = worker_id
        self.channels = channels

    def run(self):
        asyncio.run(self._async_run())

    async def _async_run(self):
        logging.basicConfig(
            level=logging.INFO,
            format=f"[Worker-{self.worker_id}] %(asctime)s %(levelname)s %(message)s",
        )
        logger.info("Worker %d starting with %d channels", self.worker_id, len(self.channels))

        sqlite_db = SQLiteDB()
        await sqlite_db.start()

        redis_writer = RedisStateWriter()
        await redis_writer.start()

        influx_writer = InfluxBatchWriter()
        try:
            await influx_writer.start()
        except Exception as e:
            logger.warning("InfluxDB not available: %s", e)

        executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix=f"worker{self.worker_id}")

        monitors = [
            ChannelMonitor(
                config=ch,
                redis_writer=redis_writer,
                influx_writer=influx_writer,
                sqlite_db=sqlite_db,
                executor=executor,
            )
            for ch in self.channels
        ]

        tasks = [asyncio.create_task(m.run()) for m in monitors]
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error("Worker %d error: %s", self.worker_id, e)
        finally:
            executor.shutdown(wait=False)
            await redis_writer.stop()
            await influx_writer.stop()
            await sqlite_db.stop()
