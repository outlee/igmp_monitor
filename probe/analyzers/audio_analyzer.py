from typing import Dict, List, Optional

import numpy as np

from config import (
    CLIP_RATIO_THRESHOLD,
    CLIP_THRESHOLD,
    SILENCE_DURATION_SEC,
    SILENCE_RMS_THRESHOLD,
    STUTTER_PTS_RATIO,
    STUTTER_RATE_THRESHOLD,
    STUTTER_WINDOW_SEC,
)


class AudioAnalyzer:
    def __init__(self):
        self.silence_start: Optional[float] = None
        # 卡顿检测状态
        self._last_pts: Optional[float] = None  # 上一帧 PTS（秒）
        self._stutter_events: List[float] = []  # 卡顿事件时间戳（单调时钟秒）

    def analyze_chunk(
        self,
        samples: np.ndarray,
        sample_rate: int,
        timestamp: float,
        pts: Optional[float] = None,
        samples_count: Optional[int] = None,
    ) -> Dict:
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

        # --- 音频卡顿检测 ---
        is_stuttering = False
        stutter_count = 0

        if pts is not None and self._last_pts is not None:
            actual_interval = pts - self._last_pts
            n_samples = samples_count if samples_count is not None else len(samples)
            expected_interval = n_samples / sample_rate if sample_rate > 0 else 0.0

            is_stutter_event = (
                actual_interval < 0  # PTS 回跳
                or (expected_interval > 0 and actual_interval > expected_interval * STUTTER_PTS_RATIO)
            )
            if is_stutter_event:
                self._stutter_events.append(timestamp)

        # 清理窗口外的旧事件
        cutoff = timestamp - STUTTER_WINDOW_SEC
        self._stutter_events = [t for t in self._stutter_events if t >= cutoff]

        stutter_count = len(self._stutter_events)
        if stutter_count >= STUTTER_RATE_THRESHOLD:
            is_stuttering = True

        if pts is not None:
            self._last_pts = pts

        return {
            "rms": rms,
            "is_silent": is_silent,
            "is_clipping": clip_ratio > CLIP_RATIO_THRESHOLD,
            "clip_ratio": clip_ratio,
            "is_stuttering": is_stuttering,
            "stutter_count": stutter_count,
        }
