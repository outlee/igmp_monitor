import time
from typing import Optional


class PCRJitterChecker:
    PCR_WRAP = (1 << 33) * 300

    def __init__(self):
        self.last_pcr: Optional[int] = None
        self.last_time: Optional[float] = None
        self.jitter_ms: float = 0.0

    def update(self, pcr: int) -> float:
        now = time.monotonic()
        if self.last_pcr is not None and self.last_time is not None:
            diff = pcr - self.last_pcr
            if diff < 0:
                diff += self.PCR_WRAP
            elapsed = now - self.last_time
            expected = elapsed * 27_000_000
            if expected > 0:
                self.jitter_ms = abs(diff - expected) / 27_000.0
        self.last_pcr = pcr
        self.last_time = now
        return self.jitter_ms

    def reset(self):
        self.last_pcr = None
        self.last_time = None
        self.jitter_ms = 0.0
