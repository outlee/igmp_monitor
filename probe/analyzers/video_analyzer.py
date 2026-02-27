import os
from typing import Dict, List, Optional

import cv2
import numpy as np

from config import (
    BLACK_LUMA_THRESHOLD,
    FREEZE_DURATION_SEC,
    FREEZE_MSE_THRESHOLD,
    MOSAIC_CORRUPT_RATIO_THRESHOLD,
    MOSAIC_DURATION_SEC,
    MOSAIC_HIGH_VAR_THRESHOLD,
    MOSAIC_LOW_VAR_THRESHOLD,
    MOSAIC_BLOCK_SIZE,
    THUMBNAIL_DIR,
    THUMBNAIL_HEIGHT,
    THUMBNAIL_QUALITY,
    THUMBNAIL_WIDTH,
)


class VideoAnalyzer:
    def __init__(self, channel_id: str, thumbnail_dir: str = THUMBNAIL_DIR):
        self.channel_id = channel_id
        self.thumbnail_dir = thumbnail_dir
        self.last_gray: Optional[np.ndarray] = None
        self.freeze_start: Optional[float] = None
        # 花屏检测状态
        self._mosaic_start: Optional[float] = None
        os.makedirs(thumbnail_dir, exist_ok=True)

    def analyze_frame(self, frame_bgr: np.ndarray, timestamp: float, corrupt_ratio: float = 0.0) -> Dict:
        result = {
            "is_black": False,
            "is_frozen": False,
            "is_mosaic": False,
            "mosaic_ratio": 0.0,
            "brightness": 0.0,
            "thumbnail_path": "",
        }

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        result["brightness"] = brightness
        result["is_black"] = brightness < BLACK_LUMA_THRESHOLD

        if self.last_gray is not None:
            diff = gray.astype(np.float32) - self.last_gray.astype(np.float32)
            mse = float(np.mean(diff * diff))
            if mse < FREEZE_MSE_THRESHOLD:
                if self.freeze_start is None:
                    self.freeze_start = timestamp
                elif timestamp - self.freeze_start > FREEZE_DURATION_SEC:
                    result["is_frozen"] = True
            else:
                self.freeze_start = None
        else:
            self.freeze_start = None

        self.last_gray = gray

        # --- 花屏检测 ---
        is_mosaic = False
        mosaic_ratio = 0.0

        # 方案A：PyAV corrupt 帧比例
        signal_a = corrupt_ratio > MOSAIC_CORRUPT_RATIO_THRESHOLD

        # 方案B：图像块方差分析
        h, w = frame_bgr.shape[:2]
        bh = h // MOSAIC_BLOCK_SIZE
        bw = w // MOSAIC_BLOCK_SIZE
        total_blocks = bh * bw

        if total_blocks > 0:
            # 向量化块方差计算
            gray_crop = gray[:bh*MOSAIC_BLOCK_SIZE, :bw*MOSAIC_BLOCK_SIZE]
            blocks = gray_crop.reshape(bh, MOSAIC_BLOCK_SIZE, bw, MOSAIC_BLOCK_SIZE)
            vars_ = blocks.var(axis=(1, 3))  # shape (bh, bw)
            low_var_count = int((vars_ < MOSAIC_LOW_VAR_THRESHOLD).sum())
            high_var_count = int((vars_ > MOSAIC_HIGH_VAR_THRESHOLD).sum())

            low_ratio = low_var_count / total_blocks
            high_ratio = high_var_count / total_blocks
            signal_b = (low_ratio > 0.30) or (high_ratio > 0.20)
            mosaic_ratio = max(low_ratio, high_ratio)
        else:
            signal_b = False

        # 任一信号持续超时 → 花屏
        if signal_a or signal_b:
            if self._mosaic_start is None:
                self._mosaic_start = timestamp
            elif timestamp - self._mosaic_start > MOSAIC_DURATION_SEC:
                is_mosaic = True
        else:
            self._mosaic_start = None

        result["is_mosaic"] = is_mosaic
        result["mosaic_ratio"] = mosaic_ratio

        is_alarm = result["is_black"] or result["is_frozen"] or result["is_mosaic"]
        thumb_path = self._save_thumbnail(frame_bgr, timestamp, is_alarm)
        result["thumbnail_path"] = thumb_path
        return result

    def _save_thumbnail(self, frame_bgr: np.ndarray, ts: float, is_alarm: bool) -> str:
        thumb = cv2.resize(frame_bgr, (THUMBNAIL_WIDTH, THUMBNAIL_HEIGHT))
        latest_path = os.path.join(self.thumbnail_dir, f"latest_{self.channel_id}.jpg")
        cv2.imwrite(latest_path, thumb, [cv2.IMWRITE_JPEG_QUALITY, THUMBNAIL_QUALITY])

        if is_alarm:
            alarm_path = os.path.join(
                self.thumbnail_dir,
                f"alarm_{self.channel_id}_{int(ts)}.jpg",
            )
            cv2.imwrite(alarm_path, thumb, [cv2.IMWRITE_JPEG_QUALITY, 85])
            return alarm_path
        return latest_path
