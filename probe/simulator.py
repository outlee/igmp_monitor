import asyncio
import io
import logging
import os
import socket
import struct
import time
from typing import Dict, List, Optional

import av
import numpy as np

logger = logging.getLogger(__name__)

FAULT_TYPES = ["BLACK_SCREEN", "FROZEN", "SILENT", "PACKET_LOSS", "BITRATE_DROP"]

_simulators: Dict[str, "StreamSimulator"] = {}


def get_simulator(channel_id: str) -> Optional["StreamSimulator"]:
    return _simulators.get(channel_id)


def register_simulator(sim: "StreamSimulator"):
    _simulators[sim.channel_id] = sim


class StreamSimulator:
    TS_PACKET_SIZE = 188
    TS_SYNC = 0x47
    PACKETS_PER_UDP = 7

    def __init__(
        self,
        channel_id: str,
        video_path: str,
        mcast_ip: str,
        mcast_port: int,
    ):
        self.channel_id = channel_id
        self.video_path = video_path
        self.mcast_ip = mcast_ip
        self.mcast_port = mcast_port
        self.active_fault: Optional[str] = None
        self.fault_until: float = 0.0
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_ts_data: bytes = b""
        register_simulator(self)

    def trigger_fault(self, fault_type: str, duration_sec: int = 30):
        if fault_type not in FAULT_TYPES:
            raise ValueError(f"Unknown fault type: {fault_type}")
        self.active_fault = fault_type
        self.fault_until = time.time() + duration_sec
        logger.info("Fault triggered: %s on %s for %ds", fault_type, self.channel_id, duration_sec)

    def clear_fault(self):
        self.active_fault = None
        self.fault_until = 0.0

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 32)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        try:
            while self._running:
                if not os.path.exists(self.video_path):
                    logger.warning("Sim video not found: %s, sleeping 5s", self.video_path)
                    await asyncio.sleep(5)
                    continue
                try:
                    await self._stream_file(sock)
                except Exception as e:
                    logger.warning("Sim stream error for %s: %s", self.channel_id, e)
                    await asyncio.sleep(2)
        finally:
            sock.close()

    async def _stream_file(self, sock: socket.socket):
        container = av.open(self.video_path, format=None)
        try:
            demux = container.demux()
            packet_buffer: List[bytes] = []
            pid_counter = 256

            for av_packet in demux:
                if not self._running:
                    break
                if av_packet.pts is None:
                    continue

                now = time.time()
                fault_active = self.active_fault and now < self.fault_until
                if fault_active and now >= self.fault_until:
                    self.active_fault = None
                    fault_active = False

                ts_data = self._wrap_in_ts(av_packet, pid_counter)
                pid_counter = (pid_counter % 0x1FFF) + 1
                if pid_counter < 256:
                    pid_counter = 256

                if fault_active:
                    ts_data = self._apply_fault(ts_data, self.active_fault)

                if ts_data:
                    self._last_ts_data = ts_data
                    sock.sendto(ts_data, (self.mcast_ip, self.mcast_port))

                if av_packet.duration and av_packet.time_base:
                    sleep_dur = float(av_packet.duration * av_packet.time_base)
                    if self.active_fault == "BITRATE_DROP":
                        sleep_dur *= 3
                    await asyncio.sleep(max(0, min(sleep_dur, 0.1)))
                else:
                    await asyncio.sleep(0.04)
        finally:
            container.close()

    def _wrap_in_ts(self, av_packet, pid: int) -> bytes:
        data = bytes(av_packet)
        ts_packets = []
        first = True
        offset = 0
        while offset < len(data):
            chunk = data[offset:offset + 184]
            offset += len(chunk)
            header = bytearray(4)
            header[0] = self.TS_SYNC
            pus = 0x40 if first else 0x00
            header[1] = pus | ((pid >> 8) & 0x1F)
            header[2] = pid & 0xFF
            header[3] = 0x10 | (len(ts_packets) % 16)
            payload = chunk.ljust(184, b"\xFF")
            ts_packets.append(bytes(header) + payload)
            first = False
        if not ts_packets:
            return b""
        result = b"".join(ts_packets)
        return result

    def _apply_fault(self, ts_data: bytes, fault_type: str) -> Optional[bytes]:
        if fault_type == "BLACK_SCREEN":
            return self._make_black_ts(ts_data)
        elif fault_type == "FROZEN":
            return self._last_ts_data if self._last_ts_data else ts_data
        elif fault_type == "SILENT":
            return self._make_silent_ts(ts_data)
        elif fault_type == "PACKET_LOSS":
            return None
        return ts_data

    def _make_black_ts(self, ts_data: bytes) -> bytes:
        result = bytearray(ts_data)
        for i in range(4, len(result), self.TS_PACKET_SIZE):
            if i + 10 < len(result):
                result[i:i + 10] = b"\x00" * 10
        return bytes(result)

    def _make_silent_ts(self, ts_data: bytes) -> bytes:
        result = bytearray(ts_data)
        for i in range(4, len(result), self.TS_PACKET_SIZE):
            if i + 10 < len(result):
                result[i:i + 10] = b"\x00" * 10
        return bytes(result)
