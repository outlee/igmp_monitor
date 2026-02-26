from typing import Dict

import numpy as np

from config import (
    CLIP_RATIO_THRESHOLD,
    CLIP_THRESHOLD,
    SILENCE_DURATION_SEC,
    SILENCE_RMS_THRESHOLD,
)


class AudioAnalyzer:
    def __init__(self):
        self.silence_start: float | None = None

    def analyze_chunk(self, samples: np.ndarray, sample_rate: int, timestamp: float) -> Dict:
        if samples.dtype != np.float32:
            normalized = samples.astype(np.float32) / 32768.0
        else:
            normalized = samples

        rms = float(np.sqrt(np.mean(normalized ** 2) + 1e-12))
        clip_ratio = float(np.mean(np.abs(normalized) >= CLIP_THRESHOLD))

        is_silent_frame = rms < SILENCE_RMS_THRESHOLD
        is_silent = False

        if is_silent_frame:
            if self.silence_start is None:
                self.silence_start = timestamp
            elif timestamp - self.silence_start > SILENCE_DURATION_SEC:
                is_silent = True
        else:
            self.silence_start = None

        return {
            "rms": rms,
            "is_silent": is_silent,
            "is_clipping": clip_ratio > CLIP_RATIO_THRESHOLD,
            "clip_ratio": clip_ratio,
        }
