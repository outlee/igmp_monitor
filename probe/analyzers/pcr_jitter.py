import time
from collections import deque
from typing import Optional


class PCRJitterChecker:
    PCR_WRAP = (1 << 33) * 300

    def __init__(self, window_size: int = 5):
        self.last_pcr: Optional[int] = None
        self.last_time: Optional[float] = None
        self.jitter_ms: float = 0.0
        # 简单滑动窗口中值滤波，减少单次异常 PCR 导致的抖动误报
        self._jitter_window: deque[float] = deque(maxlen=window_size)

    def update(self, pcr: int) -> float:
        now = time.monotonic()
        if self.last_pcr is not None and self.last_time is not None:
            diff = pcr - self.last_pcr
            if diff < 0:
                diff += self.PCR_WRAP
            elapsed = now - self.last_time
            expected = elapsed * 27_000_000
            if expected > 0:
                raw_jitter = abs(diff - expected) / 27_000.0
                self._jitter_window.append(raw_jitter)
                # 使用中值，过滤瞬时毛刺
                if len(self._jitter_window) >= 3:
                    self.jitter_ms = sorted(self._jitter_window)[len(self._jitter_window) // 2]
                else:
                    self.jitter_ms = raw_jitter
        self.last_pcr = pcr
        self.last_time = now
        return self.jitter_ms

    def reset(self):
        self.last_pcr = None
        self.last_time = None
        self.jitter_ms = 0.0
        self._jitter_window.clear()
