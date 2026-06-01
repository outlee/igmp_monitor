import asyncio
import logging
import os
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple

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
        self.ts_parser = TSParser(config.id, service_id=config.service_id)
        self.bitrate_calc = BitrateCalculator(window_sec=5.0)
        self.video_analyzer = VideoAnalyzer(config.id)
        self.audio_analyzer = AudioAnalyzer()
        self._last_frame_time = 0.0
        self._cc_window_start = time.monotonic()
        self._cc_window_count = 0
        self._prev_status: Optional[ChannelStatus] = None
        self._published_alerts: Dict[str, int] = {}  # "channel_id:alert_type" -> alert_id

    def _create_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 26_214_400)  # ~25MB for high concurrency
        sock.bind(("", self.config.multicast_port))

        iface_ip = os.getenv("MULTICAST_IFACE_IP") or os.getenv("PHYSICAL_INTERFACE_IP")

        if iface_ip:
            try:
                mreq = struct.pack(
                    "4s4s",
                    socket.inet_aton(self.config.multicast_ip),
                    socket.inet_aton(iface_ip),
                )
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                sock.setsockopt(
                    socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(iface_ip)
                )
                logger.info(
                    "Joined multicast %s on interface %s for %s",
                    self.config.multicast_ip,
                    iface_ip,
                    self.config.id,
                )
            except Exception as e:
                logger.error(
                    "Failed to join multicast on interface %s: %s. Falling back to default.",
                    iface_ip,
                    e,
                )
                mreq = struct.pack(
                    "4sL", socket.inet_aton(self.config.multicast_ip), socket.INADDR_ANY
                )
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        else:
            # Default behavior (any interface)
            mreq = struct.pack(
                "4sL", socket.inet_aton(self.config.multicast_ip), socket.INADDR_ANY
            )
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
        """使用ffmpeg子进程解码视频帧"""
        import subprocess

        try:
            # ffmpeg命令：从pipe读取TS数据，提取第一帧视频，缩放到320px宽，输出BGR24原始数据
            cmd = [
                "ffmpeg",
                "-i", "pipe:0",  # 从stdin读取
                "-vf", "fps=1,scale=320:-1",  # 提取1fps，缩放到320px宽
                "-c:v", "rawvideo",
                "-pix_fmt", "bgr24",
                "-f", "rawvideo",
                "-an",  # 禁用音频
                "-v", "error",  # 只输出错误
                "-t", "1",  # 最多读取1秒
                "pipe:1",
            ]
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                # 写入TS数据并关闭stdin
                proc.stdin.write(ts_data)
                proc.stdin.close()

                # 读取输出
                stdout_data, _ = proc.communicate(timeout=10)
                proc.wait(timeout=10)

                # 计算帧尺寸 (320 x h, 3 bytes per pixel for BGR24)
                if len(stdout_data) > 0 and len(stdout_data) % (320 * 3) == 0:
                    height = len(stdout_data) // (320 * 3)
                    frame = np.frombuffer(stdout_data, dtype=np.uint8).reshape(height, 320, 3)
                    return frame, 0.0
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
        except Exception as e:
            logger.debug("Video decode error for %s: %s", self.config.id, e)
        return None

    def _decode_audio_pts(self, ts_data: bytes) -> Optional[Tuple[np.ndarray, int, float, int]]:
        """使用ffmpeg子进程解码音频帧并返回 (samples_int16, sample_rate, pts_sec, samples_count)"""
        import subprocess

        try:
            # ffmpeg命令：从pipe读取TS数据，提取0.5秒音频，输出PCM S16LE单声道
            cmd = [
                "ffmpeg",
                "-i", "pipe:0",
                "-vn",  # 禁用视频
                "-ac", "1",  # 单声道
                "-ar", "48000",  # 采样率
                "-f", "s16le",
                "-t", "0.5",  # 0.5秒
                "-v", "error",
                "pipe:1",
            ]
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                proc.stdin.write(ts_data)
                proc.stdin.close()

                stdout_data, stderr_data = proc.communicate(timeout=10)
                proc.wait(timeout=10)

                # 解析stderr获取PTS信息
                pts_sec = 0.0
                # ffmpeg可能输出包含PTS信息的行，这里简化处理
                if len(stdout_data) > 0:
                    # S16LE = 2 bytes per sample * 48000 samples/sec = 96000 bytes/sec
                    # 0.5 sec = 48000 samples
                    samples = np.frombuffer(stdout_data, dtype=np.int16)
                    return samples, 48000, pts_sec, len(samples)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
        except Exception as e:
            logger.debug("Audio decode error for %s: %s", self.config.id, e)
        return None

    async def run(self):
        sock = None
        decode_fail_count = 0
        last_decode_fail_log = 0.0

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
                except OSError as e:
                    if now - last_decode_fail_log > 30:
                        logger.warning("Socket recreate failed for %s: %s", self.config.id, e)
                        last_decode_fail_log = now
                continue

            data = await self._recv_udp(sock)
            if data is None:
                metrics = ChannelMetrics(
                    channel_id=self.config.id,
                    channel_name=self.config.name,
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

                    # 视频解码 + 性能计时（帮助诊断 CPU 消耗）
                    t0 = time.monotonic()
                    decode_result = await loop.run_in_executor(
                        self.executor, self._decode_av_frame, chunk
                    )
                    decode_ms = (time.monotonic() - t0) * 1000
                    if decode_ms > 800:  # 单路解码超过 800ms 就值得关注
                        logger.warning("Slow video decode for %s: %.0fms", self.config.id, decode_ms)

                    if decode_result is not None:
                        decoded_img, corrupt_ratio = decode_result
                        frame_result = await self._analyze_video_frame(decoded_img, now_wall, corrupt_ratio)
                        decode_fail_count = 0
                    else:
                        decode_fail_count += 1
                        if decode_fail_count % 10 == 1 and now - last_decode_fail_log > 60:
                            logger.warning("Video decode failing repeatedly for %s (count=%d)", self.config.id, decode_fail_count)
                            last_decode_fail_log = now

                    # 音频解码（同样计时）
                    t1 = time.monotonic()
                    audio_decode_result = await loop.run_in_executor(
                        self.executor, self._decode_audio_pts, chunk
                    )
                    audio_decode_ms = (time.monotonic() - t1) * 1000
                    if audio_decode_ms > 600:
                        logger.warning("Slow audio decode for %s: %.0fms", self.config.id, audio_decode_ms)
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

                channel_name = self.config.name
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

                status = evaluate_status(metrics)
                await self._handle_status_change(metrics, status)
                last_metrics_time = now

    async def _handle_status_change(self, metrics: ChannelMetrics, status: ChannelStatus):
        await self.redis_writer.update_channel_status(metrics, status)

        try:
            await self.influx_writer.write_metrics(metrics, status)
        except Exception as e:
            # 偶尔记录警告，避免日志刷屏，但能看到问题
            if int(now) % 30 == 0:
                logger.warning("Influx write failing for %s: %s", self.config.id, e)

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
            # 记录触发告警的详细指标，便于分析误报
            logger.warning(
                "ALERT triggered: %s %s | black=%s frozen=%s silent=%s mosaic=%s "
                "cc_err=%.1f pcr_jitter=%.1f bitrate=%.0f/%.0f",
                metrics.channel_id, alert_type.value,
                metrics.is_black, metrics.is_frozen, metrics.is_silent, metrics.is_mosaic,
                metrics.cc_errors_per_sec, metrics.pcr_jitter_ms,
                metrics.bitrate_kbps, metrics.expected_bitrate_kbps
            )
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
                if int(now) % 60 == 0:
                    logger.warning("Alert upsert error for %s: %s", self.config.id, e)

        # 批量解除已恢复的告警（重构后更清晰）
        self._clear_resolved_alert(metrics, AlertType.OFFLINE, metrics.is_offline)
        self._clear_resolved_alert(metrics, AlertType.BLACK_SCREEN, metrics.is_black)
        self._clear_resolved_alert(metrics, AlertType.FROZEN, metrics.is_frozen)
        self._clear_resolved_alert(metrics, AlertType.SILENT, metrics.is_silent)
        self._clear_resolved_alert(metrics, AlertType.MOSAIC, metrics.is_mosaic)
        self._clear_resolved_alert(metrics, AlertType.AUDIO_STUTTER, metrics.is_stuttering)
        self._clear_resolved_alert(metrics, AlertType.CLIPPING, metrics.is_clipping)

        self._prev_status = status

    async def _clear_resolved_alert(self, metrics: ChannelMetrics, alert_type: AlertType, is_active: bool):
        """Helper: 如果告警已恢复，则从本地缓存移除并在数据库中 resolve"""
        if is_active:
            return
        key = f"{metrics.channel_id}:{alert_type.value}"
        self._published_alerts.pop(key, None)
        try:
            await self.sqlite_db.resolve_alert(metrics.channel_id, alert_type.value)
        except Exception:
            pass


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
