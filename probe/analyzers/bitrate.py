import collections
import time
from typing import Deque, Tuple


class BitrateCalculator:
    def __init__(self, window_sec: float = 5.0):
        self.window_sec = window_sec
        self._samples: Deque[Tuple[float, int]] = collections.deque()
        self._total_bytes = 0
        self.bitrate_kbps: float = 0.0

    def update(self, bytes_received: int, now: float | None = None) -> float:
        if now is None:
            now = time.monotonic()
        self._samples.append((now, bytes_received))
        self._total_bytes += bytes_received

        cutoff = now - self.window_sec
        while self._samples and self._samples[0][0] < cutoff:
            _, b = self._samples.popleft()
            self._total_bytes -= b

        if self.window_sec > 0:
            self.bitrate_kbps = (self._total_bytes * 8) / (self.window_sec * 1000)
        return self.bitrate_kbps

    def reset(self):
        self._samples.clear()
        self._total_bytes = 0
        self.bitrate_kbps = 0.0
